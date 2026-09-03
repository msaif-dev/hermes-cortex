"""Shared test fixtures and configuration."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _set_test_environment() -> None:
    """Ensure tests run in testing environment."""
    os.environ["APP_ENVIRONMENT"] = "testing"


@pytest.fixture
def mock_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set required environment variables for testing."""
    monkeypatch.setenv("DB_PASSWORD", "test_password")
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-test-token")
    monkeypatch.setenv("DAYTONA_API_KEY", "test-daytona-key")
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
