"""Tests for configuration module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from hermes_mcp.config import DatabaseConfig, Environment, SlackConfig


class TestDatabaseConfig:
    """Tests for DatabaseConfig."""

    def test_dsn_construction(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DB_PASSWORD", "secret123")
        config = DatabaseConfig()
        assert "localhost" in config.dsn
        assert "5432" in config.dsn
        assert "secret123" in config.dsn

    def test_port_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DB_PASSWORD", "test")
        monkeypatch.setenv("DB_PORT", "0")
        with pytest.raises(ValidationError):
            DatabaseConfig()

    def test_statement_timeout_bounds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DB_PASSWORD", "test")
        monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "500")
        with pytest.raises(ValidationError):
            DatabaseConfig()


class TestSlackConfig:
    """Tests for SlackConfig."""

    def test_valid_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-valid-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-valid-token")
        config = SlackConfig()
        assert config.bot_token.get_secret_value().startswith("xoxb-")

    def test_invalid_bot_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_BOT_TOKEN", "invalid-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-valid-token")
        with pytest.raises(ValidationError):
            SlackConfig()

    def test_invalid_app_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-valid-token")
        monkeypatch.setenv("SLACK_APP_TOKEN", "invalid-token")
        with pytest.raises(ValidationError):
            SlackConfig()


class TestEnvironment:
    """Tests for Environment enum."""

    def test_valid_environments(self) -> None:
        assert Environment.DEVELOPMENT.value == "development"
        assert Environment.PRODUCTION.value == "production"
        assert Environment.TESTING.value == "testing"
        assert Environment.STAGING.value == "staging"
