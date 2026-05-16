from __future__ import annotations

from anthropic.types import Message, TextBlock, ToolUseBlock

from ..core.anthropic_client import get_anthropic_client
from ..core.config import settings
from ..core.logging import get_logger
from ..domain.models import EventKind, Job, JobStatus
from ..repositories.job_repository import AbstractJobRepository
from .event_listener import AgentEventListener
from .rag_service import RagService
from .tool_factory import LocalTool, ToolExecutionResult, make_fs_tools

logger = get_logger(__name__)


class AgentService:
    def __init__(self, repo: AbstractJobRepository, rag: RagService | None = None) -> None:
        self._repo = repo
        self._client = get_anthropic_client()
        self._rag = rag or RagService()

    async def run(self, job: Job) -> None:
        job.status = JobStatus.RUNNING
        job.log(EventKind.AGENT_INFO, "Job started")
        self._repo.save(job)
        logger.info("[job=%s] Running (model=%s)", job.id, settings.model)

        try:
            tools = make_fs_tools(job.base_dir)
            tool_map = {tool.name: tool for tool in tools}
            listener = AgentEventListener(job)
            result_chunks: list[str] = []
            messages: list[dict[str, object]] = []
            rag_context = self._rag.build_context(prompt=job.prompt, base_dir=job.base_dir)
            if rag_context:
                job.log(
                    EventKind.AGENT_INFO,
                    "Prepared RAG and exploration context",
                )
                messages.append(
                    {
                        "role": "user",
                        "content": rag_context,
                    }
                )
                self._repo.save(job)
            messages.append({"role": "user", "content": job.prompt})
            tool_call_count = 0
            last_stop_reason: str | None = None

            for turn_number in range(1, settings.agent_max_iterations + 1):
                listener.on_turn_start(turn_number)
                response = await self._create_message(messages=messages, tools=tools)
                last_stop_reason = response.stop_reason
                text_chunks = listener.on_message(response)
                result_chunks.extend(text_chunks)
                messages.append(
                    {
                        "role": "assistant",
                        "content": [self._serialize_block(block) for block in response.content],
                    }
                )
                self._repo.save(job)

                tool_uses = [block for block in response.content if isinstance(block, ToolUseBlock)]
                if not tool_uses:
                    if response.stop_reason == "end_turn":
                        self._finalize_success(job, result_chunks)
                        return
                    if response.stop_reason == "max_tokens":
                        raise RuntimeError("Agent response hit max_tokens before completing.")
                    raise RuntimeError(f"Agent stopped with stop_reason={response.stop_reason} without finishing.")

                tool_results = []
                for tool_use in tool_uses:
                    tool_call_count += 1
                    result = await self._invoke_tool(tool_use=tool_use, tool_map=tool_map)
                    listener.on_tool_result(tool_use.name, result.content, is_error=result.is_error)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": result.content,
                            "is_error": result.is_error,
                        }
                    )
                    self._repo.save(job)

                messages.append({"role": "user", "content": tool_results})

            raise RuntimeError(f"Agent exceeded max iterations ({settings.agent_max_iterations}) without finishing; last_stop_reason={last_stop_reason}, tool_calls={tool_call_count}.")

        except Exception as exc:
            job.status = JobStatus.FAILED
            job.error = str(exc)
            job.log(EventKind.ERROR, str(exc))
            logger.exception("[job=%s] Failed: %s", job.id, exc)

        finally:
            self._repo.save(job)

    async def _create_message(self, *, messages: list[dict[str, object]], tools: list[LocalTool]) -> Message:
        return await self._client.messages.create(
            model=settings.model,
            max_tokens=settings.agent_max_tokens,
            system=settings.agent_system_prompt,
            messages=messages,
            tools=[tool.to_anthropic_tool() for tool in tools],
        )

    async def _invoke_tool(
        self,
        *,
        tool_use: ToolUseBlock,
        tool_map: dict[str, LocalTool],
    ) -> ToolExecutionResult:
        tool = tool_map.get(tool_use.name)
        if tool is None:
            return ToolExecutionResult(content=f"Unknown tool: {tool_use.name}", is_error=True)
        return await tool.invoke(tool_use.input)

    def _finalize_success(self, job: Job, result_chunks: list[str]) -> None:
        job.result = "".join(result_chunks).strip()
        job.status = JobStatus.COMPLETED
        job.log(EventKind.AGENT_INFO, "Job completed successfully")
        logger.info("[job=%s] Completed", job.id)

    @staticmethod
    def _serialize_block(block: TextBlock | ToolUseBlock) -> dict[str, object]:
        return block.model_dump(mode="json", exclude_none=True)
