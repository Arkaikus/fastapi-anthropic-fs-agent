from __future__ import annotations

import anthropic as anthropic_sdk
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    TextBlock,
    create_sdk_mcp_server,
    query,
)

from app.core.anthropic_client import get_anthropic_client
from app.core.config import settings
from app.core.logging import get_logger
from app.domain.models import EventKind, Job, JobStatus
from app.repositories.job_repository import AbstractJobRepository
from app.services.event_listener import AgentEventListener
from app.services.tool_factory import make_fs_tools

logger = get_logger(__name__)


class AgentService:
    """
    Orchestrates the full agentic loop for a job.

    The Anthropic client (cloud or Ollama) is injected via the
    singleton from app.core.anthropic_client so the backend is
    wired once at startup from environment variables.
    """

    def __init__(self, repo: AbstractJobRepository) -> None:
        self._repo = repo
        self._client = get_anthropic_client()

    async def run(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        job.log(EventKind.AGENT_INFO, "Job started")
        self._repo.save(job)
        logger.info("[job=%s] Running (model=%s)", job.id, settings.model)

        try:
            fs_tools = make_fs_tools(job.base_dir)
            server = create_sdk_mcp_server(name="fs", tools=fs_tools)
            allowed = [f"mcp__fs__{t._tool_name}" for t in fs_tools]  # noqa: SLF001

            options = ClaudeAgentOptions(
                # Pass the pre-configured client so Ollama base_url is honoured
                client=self._client,
                model=settings.model,
                mcp_servers={"fs": server},
                allowed_tools=allowed,
                include_partial_messages=True,
            )

            listener = AgentEventListener(job)
            result_chunks: list[str] = []

            async for message in query(prompt=job.prompt, options=options):
                await listener.on_message(message)
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            result_chunks.append(block.text)
                self._repo.save(job)

            job.result = "".join(result_chunks)
            job.status = JobStatus.COMPLETED
            job.log(EventKind.AGENT_INFO, "Job completed successfully")
            logger.info("[job=%s] Completed", job.id)

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.log(EventKind.ERROR, str(exc))
            logger.exception("[job=%s] Failed: %s", job.id, exc)

        finally:
            self._repo.save(job)
