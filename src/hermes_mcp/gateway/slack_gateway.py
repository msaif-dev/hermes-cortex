"""Slack Gateway integration using Slack Bolt Socket Mode.

Listens for analyst mentions and direct messages, routes to the agent orchestrator,
renders Block Kit interactive approval buttons, and delivers answers.

Requirements: FR-SLACK-001 through FR-SLACK-005, GEMINI.md §9.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import httpx
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from hermes_mcp.agent.orchestrator import AgentOrchestrator
from hermes_mcp.config import SlackConfig
from hermes_mcp.logging import get_logger

logger = get_logger(__name__)


class SlackGateway:
    """Gateway connecting Slack Socket Mode to the Agent reasoning engine."""

    def __init__(
        self,
        config: SlackConfig | None = None,
        orchestrator: AgentOrchestrator | None = None,
    ) -> None:
        self.config = config or SlackConfig()
        self.orchestrator = orchestrator or AgentOrchestrator()
        self._is_configured = bool(
            self.config.bot_token.get_secret_value() and self.config.app_token.get_secret_value()
        )

        self.app: AsyncApp | None = None
        if self._is_configured:
            self.app = AsyncApp(token=self.config.bot_token.get_secret_value())
            self._register_handlers()
        else:
            logger.info("slack_gateway_initialized_offline_mode")

    @property
    def is_configured(self) -> bool:
        """Return whether Slack tokens are properly configured."""
        return self._is_configured

    def _register_handlers(self) -> None:
        """Register event and action handlers with Slack Bolt."""
        if not self.app:
            return

        @self.app.event("app_mention")
        async def handle_mention(event: dict[str, Any], say: Any) -> None:
            user_id = event.get("user", "unknown_user")
            channel_id = event.get("channel", "general")
            text = event.get("text", "")

            # Strip bot mention tag (<@U...>)
            cleaned_text = " ".join([word for word in text.split() if not word.startswith("<@")])

            # Process attached files (FR-003 / AC-FR-003)
            files = event.get("files", [])
            downloaded_attachments: list[dict[str, Any]] = []
            for file_info in files:
                downloaded = await self.process_file_attachment(file_info)
                if downloaded:
                    downloaded_attachments.append(downloaded)

            logger.info(
                "slack_mention_received",
                user=user_id,
                channel=channel_id,
                attachments_count=len(downloaded_attachments),
            )
            response = await self.orchestrator.run_task(
                user_query=cleaned_text,
                user_id=user_id,
                channel_id=channel_id,
                attachments=downloaded_attachments,
            )
            await say(text=response, thread_ts=event.get("ts"))

        @self.app.action("approve_action")
        async def handle_approval(ack: Any, body: dict[str, Any], say: Any) -> None:
            await ack()
            action_value = body.get("actions", [{}])[0].get("value", "")
            user_id = body.get("user", {}).get("id", "unknown_user")
            logger.info("slack_approval_clicked", record_id=action_value, user=user_id)
            resolved = self.orchestrator.authorizer.resolve_approval(
                record_id=action_value,
                approved=True,
                approver=user_id,
            )
            if resolved:
                msg = f":white_check_mark: Operation `{resolved.action}` approved by <@{user_id}>."
                await say(msg)

        @self.app.action("reject_action")
        async def handle_rejection(ack: Any, body: dict[str, Any], say: Any) -> None:
            await ack()
            action_value = body.get("actions", [{}])[0].get("value", "")
            user_id = body.get("user", {}).get("id", "unknown_user")
            logger.info("slack_rejection_clicked", record_id=action_value, user=user_id)
            resolved = self.orchestrator.authorizer.resolve_approval(
                record_id=action_value,
                approved=False,
                approver=user_id,
            )
            if resolved:
                await say(f":x: Operation `{resolved.action}` rejected by <@{user_id}>.")

    async def process_file_attachment(self, file_info: dict[str, Any]) -> dict[str, Any] | None:
        """Download and validate an attached file from Slack (FR-003)."""
        filename = file_info.get("name", "attachment")
        file_size = file_info.get("size", 0)
        url_download = file_info.get("url_private_download") or file_info.get("url_private")

        # Security bounds: max 10MB, safe extensions
        allowed_extensions = {".csv", ".tsv", ".json", ".txt", ".sql", ".py", ".md"}
        ext = Path(filename).suffix.lower()
        if ext not in allowed_extensions:
            logger.warning("unsupported_attachment_extension", filename=filename, extension=ext)
            return None

        if file_size > 10 * 1024 * 1024:
            logger.warning("attachment_size_exceeded", filename=filename, size=file_size)
            return None

        workspace_dir = Path(tempfile.gettempdir()) / "hermes_workspace"
        workspace_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = Path(filename).name
        target_path = workspace_dir / safe_filename

        token = self.config.bot_token.get_secret_value()
        if url_download and token:
            try:
                headers = {"Authorization": f"Bearer {token}"}
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url_download, headers=headers)
                    if resp.status_code == httpx.codes.OK:
                        target_path.write_bytes(resp.content)
                        logger.info(
                            "attachment_downloaded_successfully",
                            filename=safe_filename,
                            path=str(target_path),
                        )
                        return {
                            "filename": safe_filename,
                            "path": str(target_path),
                            "size": len(resp.content),
                            "content_type": file_info.get("mimetype", "text/plain"),
                        }
            except Exception as e:
                logger.warning("attachment_download_failed", filename=filename, error=str(e))

        return {
            "filename": safe_filename,
            "path": str(target_path),
            "size": file_size,
            "content_type": file_info.get("mimetype", "text/plain"),
        }

    async def start(self) -> None:
        """Start the Slack Socket Mode listener."""
        if not self._is_configured or not self.app:
            logger.warning("cannot_start_slack_gateway_unconfigured")
            return

        handler = AsyncSocketModeHandler(
            self.app,
            self.config.app_token.get_secret_value(),
        )
        logger.info("starting_slack_socket_mode_gateway")
        await handler.start_async()  # type: ignore[no-untyped-call]
