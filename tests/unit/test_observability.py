"""Unit tests for the observability metrics and event systems.

Requirements: NFR-OBS-001, NFR-OBS-002, GEMINI.md §27.
"""
from __future__ import annotations

from hermes_mcp.observability.events import LifecycleEventType, emit_lifecycle_event
from hermes_mcp.observability.metrics import MetricsRegistry


class TestMetricsRegistry:
    """Tests for Prometheus Metrics Registry."""

    def test_record_task_metrics(self) -> None:
        reg = MetricsRegistry()
        reg.record_task_start()
        reg.record_task_completion(success=True, tokens=150, cost=0.003)

        assert reg.tasks_total == 1
        assert reg.tasks_succeeded == 1
        assert reg.tasks_failed == 0
        assert reg.total_tokens_spent == 150
        assert reg.total_cost_usd == 0.003

    def test_record_tool_metrics(self) -> None:
        reg = MetricsRegistry()
        reg.record_tool_execution("search_docs", 42.5, success=True)
        reg.record_tool_execution("run_sql", 120.0, success=False)

        assert reg.tool_calls_total["search_docs"] == 1
        assert reg.tool_calls_total["run_sql"] == 1
        assert reg.tool_errors_total["run_sql"] == 1

    def test_export_prometheus_text(self) -> None:
        reg = MetricsRegistry()
        reg.record_task_start()
        reg.record_task_completion(success=True)
        reg.record_tool_execution("search_docs", 30.0, success=True)

        text = reg.export_prometheus_text()
        assert "hermes_tasks_total 1" in text
        assert 'hermes_tool_calls_total{tool="search_docs"} 1' in text


class TestLifecycleEvents:
    """Tests for structured lifecycle event emission."""

    def test_emit_lifecycle_event(self) -> None:
        event = emit_lifecycle_event(
            event_type=LifecycleEventType.TASK_STARTED,
            session_id="sess_abc123",
            payload={"user": "analyst_1", "query": "forecast"},
        )
        assert event["event_type"] == "TASK_STARTED"
        assert event["session_id"] == "sess_abc123"
        assert event["payload"]["user"] == "analyst_1"
