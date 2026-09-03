"""Session memory store for managing live Slack conversation context.

Maintains multi-turn conversation state, user session boundaries,
and conversation history.

Requirements: FR-MEM-001, GEMINI.md §15.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from hermes_mcp.logging import get_logger

logger = get_logger(__name__)


class MessageItem(BaseModel):
    """A single message in the conversation context."""

    role: str = Field(..., description="Role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionContext(BaseModel):
    """Active session context for a specific user and channel."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(...)
    channel_id: str = Field(...)
    messages: list[MessageItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SessionStore:
    """Manages active conversation sessions in memory with isolation."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionContext] = {}

    def get_or_create_session(self, user_id: str, channel_id: str) -> SessionContext:
        """Retrieve existing active session or create a new one."""
        key = f"{user_id}:{channel_id}"
        if key not in self._sessions:
            session = SessionContext(user_id=user_id, channel_id=channel_id)
            self._sessions[key] = session
            logger.info("session_created", user_id=user_id, session_id=session.session_id)
        return self._sessions[key]

    def add_message(self, user_id: str, channel_id: str, role: str, content: str) -> SessionContext:
        """Append a message to the session conversation history."""
        session = self.get_or_create_session(user_id, channel_id)
        session.messages.append(MessageItem(role=role, content=content))
        session.updated_at = datetime.now(UTC)
        return session

    def clear_session(self, user_id: str, channel_id: str) -> bool:
        """Reset or clear session context."""
        key = f"{user_id}:{channel_id}"
        if key in self._sessions:
            del self._sessions[key]
            logger.info("session_cleared", user_id=user_id, channel_id=channel_id)
            return True
        return False
