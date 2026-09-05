"""Unit tests for the observability metrics and event systems.

Requirements: NFR-OBS-001, NFR-OBS-002, GEMINI.md §27.
"""

from __future__ import annotations

import httpx
import pytest

from hermes_mcp.observability.events import LifecycleEventType, emit_lifecycle_event
from hermes_mcp.observability.metrics import MetricsRegistry, start_metrics_server
from hermes_mcp.observability.tracing import (
    async_trace_span,
    get_current_trace_id,
    get_tracer,
    setup_tracing,
    trace_span,
)


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


class TestMetricsServer:
    """Tests for lightweight Prometheus HTTP metrics and health endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_server_endpoints(self) -> None:
        reg = MetricsRegistry()
        reg.record_task_start()
        reg.record_task_completion(success=True, tokens=50)

        server = await start_metrics_server(host="127.0.0.1", port=0, metrics_registry=reg)
        assigned_port = server.port
        assert server.is_running
        assert assigned_port > 0

        try:
            async with httpx.AsyncClient() as client:
                # 1. Test /metrics endpoint
                resp = await client.get(f"http://127.0.0.1:{assigned_port}/metrics")
                assert resp.status_code == 200
                assert "hermes_tasks_total 1" in resp.text
                assert "hermes_tasks_succeeded_total 1" in resp.text
                assert "text/plain" in resp.headers.get("content-type", "")

                # 2. Test /healthz endpoint
                health_resp = await client.get(f"http://127.0.0.1:{assigned_port}/healthz")
                assert health_resp.status_code == 200
                assert health_resp.json() == {"status": "ok"}

                # 3. Test 404 on unknown route
                not_found_resp = await client.get(f"http://127.0.0.1:{assigned_port}/nonexistent")
                assert not_found_resp.status_code == 404

                # 4. Test 405 on POST
                method_not_allowed = await client.post(
                    f"http://127.0.0.1:{assigned_port}/metrics", json={}
                )
                assert method_not_allowed.status_code == 405
        finally:
            await server.stop()
            assert not server.is_running


class TestTracing:
    """Tests for OpenTelemetry tracing helpers and spans."""

    def test_setup_tracing_enabled(self) -> None:
        tracer = setup_tracing(service_name="test-hermes", enabled=True)
        assert tracer is not None

    def test_setup_tracing_disabled(self) -> None:
        tracer = setup_tracing(service_name="test-hermes", enabled=False)
        assert tracer is None

    def test_trace_span_context_manager(self) -> None:
        setup_tracing(service_name="test-hermes", enabled=True)
        with trace_span("test_span", {"test_key": "test_val"}) as span:
            trace_id = get_current_trace_id()
            assert trace_id is not None
            assert len(trace_id) == 32
            assert span is not None

    @pytest.mark.asyncio
    async def test_async_trace_span_context_manager(self) -> None:
        setup_tracing(service_name="test-hermes", enabled=True)
        async with async_trace_span("async_test_span", {"component": "unit_test"}):
            trace_id = get_current_trace_id()
            assert trace_id is not None
            assert len(trace_id) == 32

    def test_get_tracer(self) -> None:
        tracer = get_tracer("test_module")
        assert tracer is not None
