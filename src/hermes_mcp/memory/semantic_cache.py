"""Semantic caching subsystem with tenant/user scoping.

Prevents redundant LLM and tool operations while ensuring strict isolation
and freshness controls.

Requirements: FR-MEM-003, GEMINI.md §16.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

import redis
from pydantic import BaseModel, Field

from hermes_mcp.logging import get_logger

logger = get_logger(__name__)


class CacheEntry(BaseModel):
    """Represents a cached query response."""

    cache_key: str
    user_id: str
    query: str
    response: str
    model: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    ttl_seconds: int = Field(default=3600)


class SemanticCache:
    """Provides user-scoped caching with optional Redis backend and in-memory fallback."""

    def __init__(
        self,
        default_ttl_s: int = 3600,
        redis_url: str | None = None,
    ) -> None:
        self.default_ttl = default_ttl_s
        self._store: dict[str, CacheEntry] = {}
        self.hits: int = 0
        self.misses: int = 0
        self._redis: Any = None

        url: str = str(redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        try:
            client = redis.Redis.from_url(url, socket_timeout=0.5)
            client.ping()
            self._redis = client
            logger.info("semantic_cache_connected_to_redis", url=url)
        except Exception as e:
            logger.info("semantic_cache_redis_offline_using_in_memory", reason=str(e))
            self._redis = None

    @property
    def is_redis_connected(self) -> bool:
        """Check if Redis backend is active."""
        return self._redis is not None

    def _generate_key(self, user_id: str, query: str, model: str) -> str:
        """Generate a deterministic, user-isolated cache key."""
        normalized_query = " ".join(query.strip().lower().split())
        digest = hashlib.sha256(f"{user_id}:{model}:{normalized_query}".encode()).hexdigest()
        return f"cache:{user_id}:{digest}"

    def get(self, user_id: str, query: str, model: str = "default") -> str | None:
        """Retrieve a cached answer if valid, unexpired, and strictly owned by user."""
        key = self._generate_key(user_id, query, model)

        # 1. Try Redis if connected
        if self._redis is not None:
            try:
                raw_data = self._redis.get(key)
                if raw_data is not None:
                    raw_str = (
                        raw_data.decode("utf-8") if isinstance(raw_data, bytes) else str(raw_data)
                    )
                    data = json.loads(raw_str)
                    if data.get("user_id") == user_id:
                        self.hits += 1
                        logger.info("cache_hit_redis", key=key, user_id=user_id)
                        return str(data.get("response", ""))
            except Exception as e:
                logger.warning("redis_cache_read_failed", key=key, error=str(e))

        # 2. In-memory store fallback
        entry = self._store.get(key)

        if entry is None:
            self.misses += 1
            return None

        # Check expiration
        now = time.time()
        if (now - entry.created_at) > entry.ttl_seconds:
            del self._store[key]
            self.misses += 1
            logger.debug("cache_entry_expired", key=key)
            return None

        # Cross-user isolation verification
        if entry.user_id != user_id:
            logger.warning(
                "cross_user_cache_leakage_prevented", requester=user_id, owner=entry.user_id
            )
            self.misses += 1
            return None

        self.hits += 1
        logger.info("cache_hit", key=key, user_id=user_id)
        return entry.response

    def set(
        self,
        user_id: str,
        query: str,
        response: str,
        model: str = "default",
        ttl_seconds: int | None = None,
    ) -> None:
        """Store an entry in the cache with user scoping."""
        key = self._generate_key(user_id, query, model)
        ttl = ttl_seconds or self.default_ttl
        entry = CacheEntry(
            cache_key=key,
            user_id=user_id,
            query=query,
            response=response,
            model=model,
            ttl_seconds=ttl,
        )
        self._store[key] = entry

        if self._redis is not None:
            try:
                self._redis.setex(
                    key,
                    ttl,
                    json.dumps(entry.model_dump(mode="json")),
                )
            except Exception as e:
                logger.warning("redis_cache_write_failed", key=key, error=str(e))

        logger.info("cache_stored", key=key, user_id=user_id)

    def clear(self) -> None:
        """Clear all cached entries."""
        if self._redis is not None:
            try:
                keys = self._redis.keys("cache:*")
                if keys:
                    self._redis.delete(*keys)
            except Exception as e:
                logger.warning("redis_cache_clear_failed", error=str(e))
        self._store.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate as a percentage."""
        total = self.hits + self.misses
        return round((self.hits / total) * 100.0, 2) if total > 0 else 0.0
