"""Prometheus metrics registry and telemetry collectors.

Tracks request throughput, tool execution latencies, token consumption,
and operational error rates.

Requirements: NFR-OBS-002, GEMINI.md §27.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class MetricsRegistry:
    """In-memory telemetry and Prometheus metrics collector."""

    tasks_total: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    tool_calls_total: dict[str, int] = field(default_factory=dict)
    tool_errors_total: dict[str, int] = field(default_factory=dict)
    tool_durations_ms: dict[str, list[float]] = field(default_factory=dict)
    total_tokens_spent: int = 0
    total_cost_usd: float = 0.0

    def record_task_start(self) -> None:
        """Increment active/total task counter."""
        self.tasks_total += 1

    def record_task_completion(self, success: bool, tokens: int = 0, cost: float = 0.0) -> None:
        """Record outcome of completed reasoning task."""
        if success:
            self.tasks_succeeded += 1
        else:
            self.tasks_failed += 1
        self.total_tokens_spent += tokens
        self.total_cost_usd += cost

    def record_tool_execution(self, tool_name: str, duration_ms: float, success: bool) -> None:
        """Record latency and outcome of tool call."""
        self.tool_calls_total[tool_name] = self.tool_calls_total.get(tool_name, 0) + 1
        if not success:
            self.tool_errors_total[tool_name] = self.tool_errors_total.get(tool_name, 0) + 1

        if tool_name not in self.tool_durations_ms:
            self.tool_durations_ms[tool_name] = []
        self.tool_durations_ms[tool_name].append(duration_ms)

    def export_prometheus_text(self) -> str:
        """Export collected metrics in standard Prometheus exposition format."""
        lines: list[str] = [
            "# HELP hermes_tasks_total Total tasks initiated",
            "# TYPE hermes_tasks_total counter",
            f"hermes_tasks_total {self.tasks_total}",
            "# HELP hermes_tasks_succeeded_total Total successfully finished tasks",
            "# TYPE hermes_tasks_succeeded_total counter",
            f"hermes_tasks_succeeded_total {self.tasks_succeeded}",
            "# HELP hermes_tasks_failed_total Total failed tasks",
            "# TYPE hermes_tasks_failed_total counter",
            f"hermes_tasks_failed_total {self.tasks_failed}",
            "# HELP hermes_tokens_spent_total Cumulative tokens consumed",
            "# TYPE hermes_tokens_spent_total counter",
            f"hermes_tokens_spent_total {self.total_tokens_spent}",
            "# HELP hermes_cost_usd_total Estimated cumulative LLM cost in USD",
            "# TYPE hermes_cost_usd_total gauge",
            f"hermes_cost_usd_total {self.total_cost_usd:.4f}",
        ]

        for tool, count in self.tool_calls_total.items():
            lines.append(f'hermes_tool_calls_total{{tool="{tool}"}} {count}')

        for tool, count in self.tool_errors_total.items():
            lines.append(f'hermes_tool_errors_total{{tool="{tool}"}} {count}')

        return "\n".join(lines) + "\n"


# Global shared registry singleton
registry = MetricsRegistry()


class MetricsServer:
    """Lightweight async HTTP server for exporting Prometheus metrics.

    Serves Prometheus-compatible metrics on /metrics and health status on /healthz.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9090,
        metrics_registry: MetricsRegistry | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.registry = metrics_registry or registry
        self._server: asyncio.Server | None = None

    async def _handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Process incoming HTTP GET requests for metrics and health checks."""
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                await writer.wait_closed()
                return

            request_line = line.decode("utf-8", errors="replace").strip()
            parts = request_line.split()
            method = parts[0] if parts else ""
            path = parts[1] if len(parts) > 1 else ""

            # Consume headers until delimiter
            while True:
                header = await reader.readline()
                if not header or header in (b"\r\n", b"\n"):
                    break

            if method != "GET":
                body = b"Method Not Allowed"
                response = (
                    b"HTTP/1.1 405 Method Not Allowed\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
            elif path == "/metrics":
                body = self.registry.export_prometheus_text().encode("utf-8")
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: text/plain; version=0.0.4; charset=utf-8\r\n"
                    b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
            elif path in ("/healthz", "/health"):
                body = b'{"status": "ok"}\n'
                response = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
            else:
                body = b"Not Found"
                response = (
                    b"HTTP/1.1 404 Not Found\r\n"
                    b"Content-Type: text/plain\r\n"
                    b"Content-Length: " + str(len(body)).encode("ascii") + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )

            writer.write(response)
            await writer.drain()
        except (ConnectionResetError, BrokenPipeError):
            pass
        except Exception as exc:
            logger.warning("metrics_server_handler_error", error=str(exc))
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as close_exc:
                logger.debug("metrics_socket_close_debug", error=str(close_exc))

    async def start(self) -> asyncio.Server:
        """Start the metrics HTTP server."""
        self._server = await asyncio.start_server(self._handle_request, self.host, self.port)
        if self._server.sockets:
            sock = self._server.sockets[0]
            self.port = sock.getsockname()[1]
        logger.info("metrics_server_started", host=self.host, port=self.port)
        return self._server

    async def stop(self) -> None:
        """Stop the metrics HTTP server cleanly."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
            logger.info("metrics_server_stopped", port=self.port)

    @property
    def is_running(self) -> bool:
        """Return True if server is actively listening."""
        return self._server is not None and self._server.is_serving()


async def start_metrics_server(
    host: str = "127.0.0.1",
    port: int = 9090,
    metrics_registry: MetricsRegistry | None = None,
) -> MetricsServer:
    """Helper to instantiate and start a MetricsServer."""
    server = MetricsServer(host=host, port=port, metrics_registry=metrics_registry)
    await server.start()
    return server
