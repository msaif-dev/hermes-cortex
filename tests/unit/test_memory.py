"""Unit tests for the memory subsystems.

Tests session store, episodic store, semantic caching with user isolation,
and vector memory.

Requirements: FR-MEM-001 through FR-MEM-004, GEMINI.md §15, §16.
"""

from __future__ import annotations

import time

from hermes_mcp.memory.episodic_store import EpisodicStore
from hermes_mcp.memory.semantic_cache import SemanticCache
from hermes_mcp.memory.session_store import SessionStore
from hermes_mcp.memory.vector_memory import VectorMemoryStore
from hermes_mcp.models import TrajectoryStep


class TestSessionStore:
    """Tests for multi-turn session store."""

    def test_session_lifecycle(self) -> None:
        store = SessionStore()
        session = store.get_or_create_session("user_1", "channel_a")
        assert session.user_id == "user_1"
        assert len(session.messages) == 0

        store.add_message("user_1", "channel_a", "user", "Hello")
        store.add_message("user_1", "channel_a", "assistant", "Hi there")
        updated = store.get_or_create_session("user_1", "channel_a")
        assert len(updated.messages) == 2

        assert store.clear_session("user_1", "channel_a") is True
        cleared = store.get_or_create_session("user_1", "channel_a")
        assert len(cleared.messages) == 0


class TestEpisodicStore:
    """Tests for episodic trace store."""

    def test_record_and_retrieve_trace(self) -> None:
        store = EpisodicStore()
        step1 = TrajectoryStep(step_number=0, thought="Step 0 thought")
        step2 = TrajectoryStep(step_number=1, thought="Step 1 thought")

        store.record_step("session_123", step1)
        store.record_step("session_123", step2)

        trace = store.get_trace("session_123")
        assert len(trace) == 2
        assert trace[0].thought == "Step 0 thought"


class TestSemanticCache:
    """Tests for semantic cache with user isolation."""

    def test_cache_hit_and_miss(self) -> None:
        cache = SemanticCache(default_ttl_s=60)
        assert cache.get("user_1", "quarterly revenue") is None

        cache.set("user_1", "quarterly revenue", "Revenue is 1.5M")
        cached = cache.get("user_1", "quarterly revenue")
        assert cached == "Revenue is 1.5M"
        assert cache.hits == 1

    def test_cross_user_isolation(self) -> None:
        cache = SemanticCache(default_ttl_s=60)
        cache.set("user_alice", "secret query", "Alice confidential data")

        # Bob queries the same exact text
        bob_result = cache.get("user_bob", "secret query")
        assert bob_result is None

    def test_cache_expiration(self) -> None:
        cache = SemanticCache(default_ttl_s=1)
        cache.set("user_1", "temp query", "temp data", ttl_seconds=1)
        time.sleep(1.1)
        assert cache.get("user_1", "temp query") is None


class TestVectorMemory:
    """Tests for long-term vector memory with user scoping."""

    def test_store_and_search_facts(self) -> None:
        mem = VectorMemoryStore()
        mem.store_fact("analyst_1", "Q3 revenue grew by 12 percent")
        mem.store_fact("analyst_1", "Operating margin is 22 percent")
        mem.store_fact("analyst_2", "Analyst 2 private note")

        results = mem.search_memory("analyst_1", "revenue")
        assert len(results) == 1
        assert "revenue" in results[0].content

        # Verify analyst 1 cannot see analyst 2's memories
        cross_results = mem.search_memory("analyst_1", "private note")
        assert len(cross_results) == 0

    def test_delete_fact(self) -> None:
        mem = VectorMemoryStore()
        fact = mem.store_fact("analyst_1", "Temporary fact to delete")
        assert mem.delete_fact("analyst_1", fact.memory_id) is True
        assert len(mem.search_memory("analyst_1", "Temporary")) == 0
