"""Task planner for multi-step problem decomposition.

Decomposes complex analytical and research requests into an ordered sequence
of executable sub-tasks, bounded by max planning steps.

Requirements: FR-AGENT-002, GEMINI.md §28, §29.
"""

from __future__ import annotations

from hermes_mcp.config import AgentConfig
from hermes_mcp.logging import get_logger

logger = get_logger(__name__)


class TaskPlanner:
    """Decomposes complex requests into sequenced sub-tasks."""

    def __init__(self, config: AgentConfig | None = None) -> None:
        self.config = config or AgentConfig()

    def create_plan(self, user_query: str) -> list[str]:
        """Decompose a query into a sequence of actionable steps.

        Bridges simple single-tool queries and complex multi-step analysis.
        """
        logger.info("creating_plan_for_query", query=user_query)
        q_lower = user_query.lower()
        steps: list[str] = []

        # Heuristic / deterministic decomposition logic
        if any(w in q_lower for w in ["database", "sql", "table", "revenue", "expense"]):
            steps.append("Search database catalog and execute read-only SQL query")

        if any(w in q_lower for w in ["doc", "policy", "report", "forecast", "guide"]):
            steps.append("Search relevant document corpus and analyst reports")

        if any(w in q_lower for w in ["code", "repo", "function", "regex", "file"]):
            steps.append("Search codebase files for target implementations")

        if any(w in q_lower for w in ["run", "calculate", "compute", "python", "script", "plot"]):
            steps.append("Execute computation or data processing script in sandbox")

        # Fallback if no specific keyword matched
        if not steps:
            steps.append(f"Execute analytical research on: {user_query}")

        steps.append("Synthesize findings and deliver structured analytical answer")

        # Enforce hard upper bound on planning steps
        bounded_steps = steps[: self.config.max_planning_steps]
        logger.info(
            "plan_generated",
            total_steps=len(bounded_steps),
            steps=bounded_steps,
        )
        return bounded_steps
