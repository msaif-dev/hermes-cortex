"""Episodic memory store for logging and retrieving agent execution trajectories.

Maintains structured traces of thoughts, actions, and observations
for multi-step problem solving, debugging, and reflexion.

Requirements: FR-MEM-002, GEMINI.md §28.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from hermes_mcp.logging import get_logger

if TYPE_CHECKING:
    from hermes_mcp.models import AgentState, TrajectoryStep

logger = get_logger(__name__)


class EpisodicStore:
    """Stores episodic execution traces for agent task sessions."""

    def __init__(self) -> None:
        self._traces: dict[str, list[TrajectoryStep]] = {}

    def record_step(self, session_id: str, step: TrajectoryStep) -> None:
        """Append an execution step to the session's episodic trace."""
        if session_id not in self._traces:
            self._traces[session_id] = []
        self._traces[session_id].append(step)
        logger.info(
            "trajectory_step_recorded",
            session_id=session_id,
            step=step.step_number,
            tool=step.tool_call.tool_name if step.tool_call else None,
            success=step.tool_result.success if step.tool_result else None,
        )

    def get_trace(self, session_id: str) -> list[TrajectoryStep]:
        """Retrieve all recorded trajectory steps for a session."""
        return list(self._traces.get(session_id, []))

    def summarize_trajectory(self, state: AgentState) -> dict[str, Any]:
        """Produce an operational summary of the reasoning run."""
        steps = self.get_trace(state.session_id)
        return {
            "session_id": state.session_id,
            "status": state.status.value,
            "total_steps": len(steps),
            "plan_length": len(state.plan),
            "tools_invoked": [s.tool_call.tool_name for s in steps if s.tool_call],
            "total_cost_usd": state.total_cost_usd,
        }

    async def persist_trace(
        self,
        session_id: str,
        state: AgentState,
        pool: Any | None = None,
    ) -> bool:
        """Persist trajectory trace to PostgreSQL JSONB table if database pool is available."""
        if pool is None:
            return False

        try:
            steps = self.get_trace(session_id)
            steps_json = json.dumps([s.model_dump(mode="json") for s in steps])
            plan_json = json.dumps(state.plan)

            query = (
                "INSERT INTO agent_trajectories "
                "(session_id, user_id, status, plan, steps, updated_at) "
                "VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, NOW()) "
                "ON CONFLICT (session_id) DO UPDATE SET "
                "status = EXCLUDED.status, "
                "plan = EXCLUDED.plan, "
                "steps = EXCLUDED.steps, "
                "updated_at = NOW()"
            )
            async with pool.acquire() as conn:
                await conn.execute(
                    query,
                    session_id,
                    state.user_query[:64] or "unknown_user",
                    state.status.value,
                    plan_json,
                    steps_json,
                )
            logger.info("episodic_trace_persisted_to_db", session_id=session_id)
        except Exception as e:
            logger.warning("episodic_trace_db_persist_failed", session_id=session_id, error=str(e))
            return False
        else:
            return True
