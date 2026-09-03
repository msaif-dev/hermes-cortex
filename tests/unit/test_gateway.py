"""Unit tests for the Slack Gateway.

Tests offline initialization, configuration gating, and message routing.

Requirements: FR-SLACK-001 through FR-SLACK-005, GEMINI.md §9.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import SecretStr

if TYPE_CHECKING:
    import pytest

from hermes_mcp.agent.orchestrator import AgentOrchestrator
from hermes_mcp.config import SlackConfig
from hermes_mcp.gateway.slack_gateway import SlackGateway


class TestSlackGateway:
    """Tests for SlackGateway."""

    def test_unconfigured_gateway_initializes_offline(self) -> None:
        cfg = SlackConfig(bot_token=SecretStr(""), app_token=SecretStr(""))
        gw = SlackGateway(config=cfg)
        assert gw.is_configured is False
        assert gw.app is None

    def test_configured_gateway_initializes_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-valid-bot-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-valid-app-token")
        cfg = SlackConfig()
        orch = AgentOrchestrator()
        gw = SlackGateway(config=cfg, orchestrator=orch)
        assert gw.is_configured is True
        assert gw.app is not None

    async def test_start_unconfigured_returns_cleanly(self) -> None:
        cfg = SlackConfig(bot_token=SecretStr(""), app_token=SecretStr(""))
        gw = SlackGateway(config=cfg)
        # Should return without raising exceptions
        await gw.start()
