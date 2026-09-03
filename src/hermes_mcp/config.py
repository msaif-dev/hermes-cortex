"""Application configuration with validation and fail-fast behavior.

All configuration is loaded from environment variables and/or .env files.
No secrets are hardcoded. Configuration is validated at startup.

Requirements: GEMINI.md §26, NFR-SEC-001
"""

from __future__ import annotations

import enum

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(enum.StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    name: str = Field(default="hermes", description="Database name")
    user: str = Field(default="hermes_readonly", description="Database user")
    password: SecretStr = Field(default=SecretStr(""), description="Database password")
    min_connections: int = Field(default=2, ge=1, le=20)
    max_connections: int = Field(default=10, ge=1, le=100)
    statement_timeout_ms: int = Field(
        default=30000,
        ge=1000,
        le=300000,
        description="SQL statement timeout in ms",
    )
    ssl_mode: str = Field(
        default="prefer",
        description="SSL mode for database connection",
    )

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"


class SlackConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SLACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    bot_token: SecretStr = Field(
        default=SecretStr(""),
        description="Slack Bot Token (xoxb-...)",
    )
    app_token: SecretStr = Field(
        default=SecretStr(""),
        description="Slack App-Level Token (xapp-...)",
    )

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, v: SecretStr) -> SecretStr:
        val = v.get_secret_value()
        if val and not val.startswith("xoxb-"):
            raise ValueError("Bot token must start with 'xoxb-'")
        return v

    @field_validator("app_token")
    @classmethod
    def validate_app_token(cls, v: SecretStr) -> SecretStr:
        val = v.get_secret_value()
        if val and not val.startswith("xapp-"):
            raise ValueError("App token must start with 'xapp-'")
        return v


class DaytonaConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DAYTONA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="Daytona API key",
    )
    api_url: str = Field(default="https://app.daytona.io/api", description="Daytona API URL")
    target: str = Field(default="us", description="Daytona target region")
    default_image: str = Field(
        default="python:3.11-slim",
        description="Default sandbox image",
    )
    cpu: int = Field(default=2, ge=1, le=8, description="Default sandbox CPU count")
    memory: int = Field(default=4, ge=1, le=32, description="Default sandbox memory (GiB)")
    disk: int = Field(default=10, ge=5, le=100, description="Default sandbox disk (GiB)")
    execution_timeout_s: int = Field(
        default=60,
        ge=5,
        le=600,
        description="Execution timeout in seconds",
    )
    auto_stop_interval_min: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Auto-stop interval in minutes",
    )
    network_block_all: bool = Field(
        default=True,
        description="Block all outbound network in sandboxes",
    )


class LLMConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LLM_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    provider: str = Field(default="openai", description="LLM provider")
    model: str = Field(default="gpt-4", description="Model name")
    api_key: SecretStr = Field(
        default=SecretStr(""),
        description="LLM API key",
    )
    api_base: str | None = Field(
        default=None,
        description="Custom API base URL",
    )
    max_tokens: int = Field(default=4096, ge=100, le=128000)
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_s: int = Field(default=60, ge=5, le=300)
    max_cost_per_task_usd: float = Field(
        default=1.0,
        ge=0.01,
        le=100.0,
        description="Max cost per task in USD",
    )


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    max_planning_steps: int = Field(default=10, ge=1, le=50)
    max_tool_calls: int = Field(default=20, ge=1, le=100)
    max_retries: int = Field(default=3, ge=0, le=10)
    max_execution_time_s: int = Field(default=120, ge=10, le=600)
    max_recursive_depth: int = Field(default=3, ge=1, le=10)


class ObservabilityConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OBS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    metrics_enabled: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    tracing_enabled: bool = Field(default=False)
    tracing_endpoint: str | None = Field(default=None)


class AppConfig(BaseSettings):
    """Root application configuration.

    Validates all configuration at startup. Fails fast on invalid config.
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Field(default=Environment.DEVELOPMENT)
    service_name: str = Field(default="hermes-mcp-platform")

    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    daytona: DaytonaConfig = Field(default_factory=DaytonaConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
