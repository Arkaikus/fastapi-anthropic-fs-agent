from __future__ import annotations

from anthropic.types import Message, TextBlock, ToolUseBlock

from ..core.logging import get_logger
from ..domain.models import EventKind, Job

logger = get_logger(__name__)


class AgentEventListener:
    def __init__(self, job: Job) -> None:
        self._job = job

    def on_turn_start(self, turn_number: int) -> None:
        self._job.log(EventKind.AGENT_INFO, f"Agent turn {turn_number} started")

    def on_message(self, message: Message) -> list[str]:
        logger.debug("[job=%s] Anthropic stop_reason=%s", self._job.id, message.stop_reason)
        self._job.log(
            EventKind.AGENT_INFO,
            f"Agent turn completed with stop_reason={message.stop_reason or 'unknown'}",
        )

        text_chunks: list[str] = []
        for block in message.content or []:
            if isinstance(block, TextBlock) and block.text.strip():
                preview = block.text.strip()[:120]
                text_chunks.append(block.text)
                self._job.log(EventKind.TEXT_DELTA, preview)
                logger.info("[job=%s] Assistant: %s", self._job.id, preview)
            elif isinstance(block, ToolUseBlock):
                self._job.log(EventKind.TOOL_START, f"Tool started: {block.name}")
                logger.info("[job=%s] Tool started: %s", self._job.id, block.name)
        return text_chunks

    def on_tool_result(self, tool_name: str, detail: str, *, is_error: bool) -> None:
        kind = EventKind.ERROR if is_error else EventKind.TOOL_END
        self._job.log(kind, f"{tool_name}: {detail}")
