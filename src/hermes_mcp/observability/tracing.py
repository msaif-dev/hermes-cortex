"""OpenTelemetry distributed tracing configuration and span utilities.

Provides trace instrumentation across gateway, agent reasoning loop,
and MCP tool execution.

Requirements: FR-020, NFR-OBS-001, GEMINI.md §27.
"""

from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

logger = structlog.get_logger(__name__)

# Try importing opentelemetry; fallback to graceful no-op if not present
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider

    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False
    trace = None  # type: ignore[assignment]
    Resource = None  # type: ignore[assignment,misc]
    TracerProvider = None  # type: ignore[assignment,misc]

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (  # type: ignore[import-not-found]
        OTLPSpanExporter as _OTLPSpanExporter,
    )
    from opentelemetry.sdk.trace.export import (
        BatchSpanProcessor as _BatchSpanProcessor,
    )

    OTLPSpanExporter: Any = _OTLPSpanExporter
    BatchSpanProcessor: Any = _BatchSpanProcessor
    _HAS_OTLP = True
except (ImportError, ModuleNotFoundError):
    _HAS_OTLP = False
    OTLPSpanExporter = None
    BatchSpanProcessor = None


class _TracingManager:
    """Internal singleton tracking OpenTelemetry tracing lifecycle."""

    def __init__(self) -> None:
        self.is_initialized: bool = False
        self.service_name: str = "hermes-mcp-platform"


_state = _TracingManager()


def setup_tracing(
    service_name: str = "hermes-mcp-platform",
    endpoint: str | None = None,
    enabled: bool = True,
) -> Any:
    """Initialize OpenTelemetry tracer provider and exporter.

    Returns the configured tracer or None if disabled/unsupported.
    """
    if not enabled or not _HAS_OTEL or trace is None or TracerProvider is None:
        _state.is_initialized = False
        return None

    try:
        resource = Resource.create({SERVICE_NAME: service_name})
        provider = TracerProvider(resource=resource)

        if (
            endpoint
            and _HAS_OTLP
            and OTLPSpanExporter is not None
            and BatchSpanProcessor is not None
        ):
            exporter = OTLPSpanExporter(endpoint=endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        elif endpoint:
            logger.warning("otlp_exporter_not_installed", endpoint=endpoint)

        trace.set_tracer_provider(provider)
        _state.is_initialized = True
        _state.service_name = service_name
        logger.info("tracing_initialized", service_name=service_name)
        return trace.get_tracer(service_name)
    except Exception as exc:
        logger.warning("tracing_setup_failed", error=str(exc))
        _state.is_initialized = False
        return None


def get_tracer(name: str = "hermes_mcp") -> Any:
    """Return active OpenTelemetry tracer or None if unavailable."""
    if _HAS_OTEL and trace is not None:
        return trace.get_tracer(name)
    return None


def get_current_trace_id() -> str | None:
    """Return active OpenTelemetry trace ID as 32-character hex string for logging."""
    if not _HAS_OTEL or trace is None:
        return None
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, "032x")
    return None


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[Any]:
    """Synchronous context manager creating a traced OpenTelemetry span."""
    if not _HAS_OTEL or trace is None:
        yield None
        return

    tracer = trace.get_tracer("hermes_mcp")
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, val in attributes.items():
                if val is not None:
                    span.set_attribute(key, str(val))
        yield span


@asynccontextmanager
async def async_trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> AsyncIterator[Any]:
    """Asynchronous context manager creating a traced OpenTelemetry span."""
    if not _HAS_OTEL or trace is None:
        yield None
        return

    tracer = trace.get_tracer("hermes_mcp")
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, val in attributes.items():
                if val is not None:
                    span.set_attribute(key, str(val))
        yield span
