"""Data models and contracts for Hermes MCP Platform.

Implements schema-first data structures for tool interactions,
agent state trajectories, memory items, and audit trails.

Requirements: GEMINI.md §4, §11, §28; plan.md Phase 5.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ErrorCategory(enum.StrEnum):
    """Classification of errors occurring during tool or agent execution."""

    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT = "TIMEOUT"
    EXECUTION_ERROR = "EXECUTION_ERROR"
    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMITED = "RATE_LIMITED"


class AgentStatus(enum.StrEnum):
    """Lifecycle status of the agent reasoning process."""

    PENDING = "PENDING"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    EVALUATING = "EVALUATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class ToolCall(BaseModel):
    """Represents a validated tool execution request."""

    call_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = Field(..., pattern=r"^[a-zA-Z0-9_-]+$")
    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout_s: int = Field(default=30, ge=1, le=300)
    caller_id: str = Field(default="system")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolResult(BaseModel):
    """Normalized response from an MCP tool execution."""

    call_id: str
    tool_name: str
    success: bool
    content: str
    error_category: ErrorCategory | None = None
    execution_time_ms: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrajectoryStep(BaseModel):
    """Represents a single step in the agent's reasoning trace."""

    step_number: int = Field(ge=0)
    thought: str = Field(default="")
    tool_call: ToolCall | None = None
    tool_result: ToolResult | None = None
    completed: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentState(BaseModel):
    """Represents the complete runtime state and trajectory of an agent session."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: AgentStatus = Field(default=AgentStatus.PENDING)
    user_query: str = Field(default="")
    current_step: int = Field(default=0, ge=0)
    plan: list[str] = Field(default_factory=list)
    steps: list[TrajectoryStep] = Field(default_factory=list)
    total_tokens_used: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryItem(BaseModel):
    """Represents a knowledge or fact item stored in episodic or long-term memory."""

    memory_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(...)
    session_id: str = Field(default="")
    content: str = Field(...)
    source: str = Field(default="agent_observation")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AuditRecord(BaseModel):
    """Immutable audit trail record for high-risk or tool execution actions."""

    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor: str = Field(...)
    action: str = Field(...)
    target: str = Field(...)
    parameters: dict[str, Any] = Field(default_factory=dict)
    outcome: str = Field(default="SUCCESS")
    risk_level: str = Field(default="LOW")
    approval_required: bool = False
    approver: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
