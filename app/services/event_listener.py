from __future__ import annotations
from typing import Any

from claude_agent_sdk import AssistantMessage, TextBlock
from claude_agent_sdk.types import StreamEvent

from app.domain.models import EventKind, Job
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentEventListener:
    """
    Translates raw SDK messages (StreamEvent, AssistantMessage) into
    structured AgentEvent entries on the Job domain model.
    """

    def __init__(self, job: Job) -> None:
        self._job = job

    async def on_message(self, message: Any) -> None:
        if isinstance(message, StreamEvent):
            await self._handle_stream_event(message)
        elif isinstance(message, AssistantMessage):
            self._handle_assistant_message(message)

    async def _handle_stream_event(self, message: StreamEvent) -> None:
        event = message.event
        etype = event.get("type", "")
        logger.debug("[job=%s] StreamEvent: %s", self._job.id, etype)

        if etype == "content_block_start":
            block = event.get("content_block", {})
            if block.get("type") == "tool_use":
                self._job.log(EventKind.TOOL_START, f"Calling tool: {block.get('name')}")

        elif etype == "content_block_stop":
            self._job.log(EventKind.TOOL_END, "Tool call finished")

        elif etype == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "").strip()
                if text:
                    self._job.log(EventKind.TEXT_DELTA, text)

        elif etype == "message_start":
            self._job.log(EventKind.AGENT_INFO, "Agent turn started")

        elif etype == "message_stop":
            self._job.log(EventKind.AGENT_INFO, "Agent turn completed")

    def _handle_assistant_message(self, message: AssistantMessage) -> None:
        for block in message.content:
            if isinstance(block, TextBlock) and block.text.strip():
                preview = block.text[:120]
                logger.info("[job=%s] Assistant: %s", self._job.id, preview)
                self._job.log(EventKind.AGENT_INFO, f"Assistant: {preview}")
