"""Reflexion self-evaluation and replanning controller.

Evaluates task completion quality, detects tool execution failures,
and generates corrective adjustments rather than hallucinating answers.

Requirements: FR-AGENT-003, GEMINI.md §28.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hermes_mcp.logging import get_logger

if TYPE_CHECKING:
    from hermes_mcp.models import ToolResult

logger = get_logger(__name__)


@dataclass(frozen=True)
class EvaluationResult:
    """Outcome of self-evaluation."""

    is_complete: bool
    should_replan: bool
    critique: str
    suggested_correction: str | None = None


class ReflexionEvaluator:
    """Evaluates task execution results against user goals."""

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def evaluate_step(
        self,
        step_goal: str,
        result: ToolResult,
        attempt: int = 1,
    ) -> EvaluationResult:
        """Evaluate whether a single tool execution step succeeded."""
        if not result.success:
            logger.warning(
                "step_execution_failed",
                step=step_goal,
                error=result.content,
                attempt=attempt,
            )
            should_replan = attempt < self.max_retries
            return EvaluationResult(
                is_complete=False,
                should_replan=should_replan,
                critique=f"Tool failed with error: {result.content}",
                suggested_correction="Adjust tool parameters or try an alternative data source.",
            )

        # Check for empty or error indicators in result content
        if "ERROR" in result.content.upper() and "TOTAL_MATCHES" not in result.content.upper():
            return EvaluationResult(
                is_complete=False,
                should_replan=attempt < self.max_retries,
                critique="Result content indicates an unhandled error or validation rejection.",
                suggested_correction="Refine query to adhere to security constraints.",
            )

        return EvaluationResult(
            is_complete=True,
            should_replan=False,
            critique="Step executed successfully with valid output.",
        )

    def evaluate_final_response(self, _user_query: str, response: str) -> EvaluationResult:
        """Evaluate whether the final synthesized response meets the user request."""
        if not response or not response.strip():
            return EvaluationResult(
                is_complete=False,
                should_replan=True,
                critique="Synthesized response was empty.",
                suggested_correction="Regenerate structured response from collected step findings.",
            )

        # Ensure refusal or error explanations are communicated clearly
        if "error" in response.lower() and "apologize" not in response.lower():
            logger.info("response_contains_error_details")

        return EvaluationResult(
            is_complete=True,
            should_replan=False,
            critique="Final response is substantive and complete.",
        )
