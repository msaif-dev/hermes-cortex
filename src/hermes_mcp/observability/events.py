"""Structured lifecycle events for observability and audit compliance.

Emits structured logs and audit telemetry across every stage
of the agent reasoning trajectory.

Requirements: GEMINI.md §27, NFR-OBS-001.
"""
from __future__ import annotations

import enum
from datetime import UTC, datetime
from typing import Any

from hermes_mcp.logging import get_logger

logger = get_logger(__name__)


class LifecycleEventType(enum.StrEnum):
    """Categorized lifecycle events in the agent execution loop."""
    TASK_STARTED = "TASK_STARTED"
    PLAN_FORMULATED = "PLAN_FORMULATED"
    TOOL_DISPATCHED = "TOOL_DISPATCHED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    REFLEXION_TRIGGERED = "REFLEXION_TRIGGERED"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_RESOLVED = "APPROVAL_RESOLVED"
    TASK_COMPLETED = "TASK_COMPLETED"
    SECURITY_VIOLATION = "SECURITY_VIOLATION"


def emit_lifecycle_event(
    event_type: LifecycleEventType,
    session_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Emit a structured lifecycle event to logging and tracing collectors."""
    event = {
        "event_type": event_type.value,
        "session_id": session_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "payload": payload or {},
    }
    logger.info(
        "agent_lifecycle_event",
        event_type=event_type.value,
        session_id=session_id,
        payload=payload,
    )
    return event
