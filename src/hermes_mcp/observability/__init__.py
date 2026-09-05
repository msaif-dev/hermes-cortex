"""Observability module for metrics collection and lifecycle event logging.

Requirements: NFR-OBS-001, NFR-OBS-002, GEMINI.md §27.
"""

from hermes_mcp.observability.events import LifecycleEventType, emit_lifecycle_event
from hermes_mcp.observability.metrics import (
    MetricsRegistry,
    MetricsServer,
    registry,
    start_metrics_server,
)
from hermes_mcp.observability.tracing import (
    async_trace_span,
    get_current_trace_id,
    get_tracer,
    setup_tracing,
    trace_span,
)

__all__ = [
    "LifecycleEventType",
    "MetricsRegistry",
    "MetricsServer",
    "async_trace_span",
    "emit_lifecycle_event",
    "get_current_trace_id",
    "get_tracer",
    "registry",
    "setup_tracing",
    "start_metrics_server",
    "trace_span",
]
