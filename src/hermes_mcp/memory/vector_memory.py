"""Long-term vector memory store with tenant/user isolation.

Stores and retrieves persistent facts, observations, and analytical summaries.
Prevents cross-user memory leakage.

Requirements: FR-MEM-004, GEMINI.md §15.
"""

from __future__ import annotations

from typing import Any

from hermes_mcp.logging import get_logger
from hermes_mcp.models import MemoryItem

logger = get_logger(__name__)


class VectorMemoryStore:
    """Manages long-term memory items with strict user scoping."""

    def __init__(self) -> None:
        self._items: dict[str, list[MemoryItem]] = {}

    def store_fact(
        self,
        user_id: str,
        content: str,
        source: str = "agent_observation",
        confidence: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryItem:
        """Store a new knowledge item strictly bound to user_id."""
        item = MemoryItem(
            user_id=user_id,
            content=content,
            source=source,
            confidence=confidence,
            metadata=metadata or {},
        )
        if user_id not in self._items:
            self._items[user_id] = []
        self._items[user_id].append(item)
        logger.info("memory_fact_stored", user_id=user_id, memory_id=item.memory_id)
        return item

    def search_memory(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        min_confidence: float = 0.5,
    ) -> list[MemoryItem]:
        """Search user's memory facts using keyword and token matching.

        Enforces strict user isolation: cannot see other users' memories.
        """
        user_memories = self._items.get(user_id, [])
        query_terms = set(query.lower().split())

        scored_items: list[tuple[int, MemoryItem]] = []
        for item in user_memories:
            if item.confidence < min_confidence:
                continue

            content_lower = item.content.lower()
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0 or query.lower() in content_lower:
                scored_items.append((score, item))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        results = [item for _, item in scored_items[:limit]]
        logger.info(
            "memory_search_completed",
            user_id=user_id,
            matches=len(results),
            query=query,
        )
        return results

    def delete_fact(self, user_id: str, memory_id: str) -> bool:
        """Delete a specific memory item owned by the user."""
        user_memories = self._items.get(user_id, [])
        for i, item in enumerate(user_memories):
            if item.memory_id == memory_id:
                user_memories.pop(i)
                logger.info("memory_fact_deleted", user_id=user_id, memory_id=memory_id)
                return True
        return False
