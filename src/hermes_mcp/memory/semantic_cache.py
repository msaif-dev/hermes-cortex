"""Semantic caching subsystem with tenant/user scoping.

Prevents redundant LLM and tool operations while ensuring strict isolation
and freshness controls.

Requirements: FR-MEM-003, GEMINI.md §16.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

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
    """Provides user-scoped caching to cut redundant model calls safely."""

    def __init__(self, default_ttl_s: int = 3600) -> None:
        self.default_ttl = default_ttl_s
        self._store: dict[str, CacheEntry] = {}
        self.hits: int = 0
        self.misses: int = 0

    def _generate_key(self, user_id: str, query: str, model: str) -> str:
        """Generate a deterministic, user-isolated cache key."""
        normalized_query = " ".join(query.strip().lower().split())
        digest = hashlib.sha256(f"{user_id}:{model}:{normalized_query}".encode()).hexdigest()
        return f"cache:{user_id}:{digest}"

    def get(self, user_id: str, query: str, model: str = "default") -> str | None:
        """Retrieve a cached answer if valid, unexpired, and strictly owned by user."""
        key = self._generate_key(user_id, query, model)
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
        entry = CacheEntry(
            cache_key=key,
            user_id=user_id,
            query=query,
            response=response,
            model=model,
            ttl_seconds=ttl_seconds or self.default_ttl,
        )
        self._store[key] = entry
        logger.info("cache_stored", key=key, user_id=user_id)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()
        self.hits = 0
        self.misses = 0

    @property
    def hit_rate(self) -> float:
        """Return cache hit rate as a percentage."""
        total = self.hits + self.misses
        return round((self.hits / total) * 100.0, 2) if total > 0 else 0.0
