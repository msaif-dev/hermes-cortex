"""Unit tests for tool authorizer and HITL controls.

Requirements: GEMINI.md §11, §14; SEC-007, SEC-008.
"""

from __future__ import annotations

from hermes_mcp.security.authorizer import RiskLevel, ToolAuthorizer


class TestToolAuthorizer:
    """Tests for ToolAuthorizer."""

    def test_tool_allowlist_permits_allowed_tool(self) -> None:
        auth = ToolAuthorizer()
        assert auth.is_tool_allowed("search_docs")
        assert auth.is_tool_allowed("run_sql")

    def test_tool_allowlist_blocks_unauthorized_tool(self) -> None:
        auth = ToolAuthorizer()
        assert not auth.is_tool_allowed("unapproved_hack_tool")

    def test_risk_classification(self) -> None:
        auth = ToolAuthorizer()
        assert auth.get_risk_level("search_docs") == RiskLevel.LOW
        assert auth.get_risk_level("run_python") == RiskLevel.MEDIUM
        assert auth.get_risk_level("drop_table") == RiskLevel.CRITICAL

    def test_approval_workflow(self) -> None:
        auth = ToolAuthorizer()
        record = auth.request_approval(
            actor="analyst_alice",
            tool_name="drop_table",
            arguments={"table": "old_logs"},
        )
        assert record.outcome == "PENDING_APPROVAL"
        assert record.approval_required is True

        resolved = auth.resolve_approval(
            record_id=record.record_id,
            approved=True,
            approver="admin_bob",
        )
        assert resolved is not None
        assert resolved.outcome == "APPROVED"
        assert resolved.approver == "admin_bob"

    def test_audit_trail_recorded(self) -> None:
        auth = ToolAuthorizer()
        auth.record_execution(
            actor="analyst_alice",
            tool_name="search_docs",
            arguments={"query": "forecast"},
            success=True,
        )
        assert len(auth.audit_trail) == 1
        assert auth.audit_trail[0].outcome == "SUCCESS"
