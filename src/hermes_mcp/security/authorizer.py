"""Security authorizer and Human-In-The-Loop (HITL) approval controller.

Enforces deterministic tool allowlisting, least-privilege checks,
and human approval requirements for high-risk actions.

Requirements: GEMINI.md §10, §11, §14; SEC-007, SEC-008.
"""

from __future__ import annotations

import enum
from typing import Any

from hermes_mcp.logging import get_logger
from hermes_mcp.models import AuditRecord

logger = get_logger(__name__)


class RiskLevel(enum.StrEnum):
    """Risk classification for tools and actions."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# Default approved tool allowlist
DEFAULT_TOOL_ALLOWLIST: set[str] = {
    "search_docs",
    "run_sql",
    "list_tables",
    "search_code",
    "run_python",
    "memory_search",
    "memory_store",
}

# Operations that strictly require human confirmation before execution
_HIGH_RISK_TOOLS: dict[str, RiskLevel] = {
    "run_python": RiskLevel.MEDIUM,
    "drop_table": RiskLevel.CRITICAL,
    "delete_data": RiskLevel.CRITICAL,
    "write_file": RiskLevel.HIGH,
}


class ToolAuthorizer:
    """Controls access to external tools and manages approval workflows."""

    def __init__(self, allowed_tools: set[str] | None = None) -> None:
        self.allowed_tools = allowed_tools or set(DEFAULT_TOOL_ALLOWLIST)
        self._audit_log: list[AuditRecord] = []
        self._pending_approvals: dict[str, AuditRecord] = {}

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is explicitly permitted by the allowlist."""
        allowed = tool_name in self.allowed_tools
        if not allowed:
            logger.warning("unauthorized_tool_attempt", tool=tool_name)
        return allowed

    def get_risk_level(self, tool_name: str, _arguments: dict[str, Any] | None = None) -> RiskLevel:
        """Evaluate the risk classification of an intended tool call."""
        if tool_name in _HIGH_RISK_TOOLS:
            return _HIGH_RISK_TOOLS[tool_name]
        return RiskLevel.LOW

    def requires_approval(self, tool_name: str, arguments: dict[str, Any] | None = None) -> bool:
        """Determine if a tool call requires explicit Human-In-The-Loop approval."""
        risk = self.get_risk_level(tool_name, arguments)
        return risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)

    def request_approval(
        self,
        actor: str,
        tool_name: str,
        arguments: dict[str, Any],
        target: str = "environment",
    ) -> AuditRecord:
        """Create a pending approval request for a high-impact operation."""
        risk = self.get_risk_level(tool_name, arguments)
        record = AuditRecord(
            actor=actor,
            action=tool_name,
            target=target,
            parameters=arguments,
            outcome="PENDING_APPROVAL",
            risk_level=risk.value,
            approval_required=True,
        )
        self._pending_approvals[record.record_id] = record
        self._audit_log.append(record)
        logger.info(
            "approval_requested",
            record_id=record.record_id,
            tool=tool_name,
            risk=risk.value,
        )
        return record

    def resolve_approval(
        self,
        record_id: str,
        approved: bool,
        approver: str,
    ) -> AuditRecord | None:
        """Record the resolution of an approval request."""
        record = self._pending_approvals.pop(record_id, None)
        if not record:
            logger.warning("approval_record_not_found", record_id=record_id)
            return None

        record.approver = approver
        record.outcome = "APPROVED" if approved else "REJECTED"
        logger.info(
            "approval_resolved",
            record_id=record_id,
            approved=approved,
            approver=approver,
        )
        return record

    def record_execution(
        self,
        actor: str,
        tool_name: str,
        arguments: dict[str, Any],
        success: bool,
    ) -> AuditRecord:
        """Record a completed tool execution in the immutable audit log."""
        risk = self.get_risk_level(tool_name, arguments)
        record = AuditRecord(
            actor=actor,
            action=tool_name,
            target="mcp_server",
            parameters=arguments,
            outcome="SUCCESS" if success else "FAILED",
            risk_level=risk.value,
            approval_required=False,
        )
        self._audit_log.append(record)
        return record

    @property
    def audit_trail(self) -> list[AuditRecord]:
        """Return the immutable audit log."""
        return list(self._audit_log)
