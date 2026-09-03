"""Prometheus metrics registry and telemetry collectors.

Tracks request throughput, tool execution latencies, token consumption,
and operational error rates.

Requirements: NFR-OBS-002, GEMINI.md §27.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
