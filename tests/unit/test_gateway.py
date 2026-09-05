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

    async def test_process_file_attachment_valid_csv(self) -> None:
        gw = SlackGateway()
        file_info = {
            "name": "data.csv",
            "size": 1024,
            "mimetype": "text/csv",
        }
        res = await gw.process_file_attachment(file_info)
        assert res is not None
        assert res["filename"] == "data.csv"
        assert res["size"] == 1024

    async def test_process_file_attachment_rejects_disallowed_extension(self) -> None:
        gw = SlackGateway()
        file_info = {
            "name": "malicious.exe",
            "size": 1024,
            "mimetype": "application/octet-stream",
        }
        res = await gw.process_file_attachment(file_info)
        assert res is None

    async def test_process_file_attachment_rejects_oversized_file(self) -> None:
        gw = SlackGateway()
        file_info = {
            "name": "huge.csv",
            "size": 25 * 1024 * 1024,  # 25 MB
            "mimetype": "text/csv",
        }
        res = await gw.process_file_attachment(file_info)
        assert res is None
