# AGENTS.md

## Purpose
- This repository exposes a FastAPI API that schedules filesystem-oriented agent jobs.
- The active agent implementation lives in the application codebase and uses the Anthropic Messages API directly instead of Claude CLI or `claude_agent_sdk`.
- Backend selection is configuration-driven through `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, and `MODEL`, which allows the same loop to target Anthropic-hosted models or an Ollama endpoint.

## Source map
- Entrypoint: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/main.py`
- App factory and routing: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/app/factory.py`
- HTTP endpoints: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/app/api/routers/`
- Agent loop orchestration: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/app/services/agent_service.py`
- Tool registry and sandboxed filesystem operations: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/app/services/tool_factory.py`
- Job/event models: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/app/domain/models.py`
- Repository abstraction: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/app/repositories/job_repository.py`
- Runtime configuration and Anthropic client wiring: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/app/core/`

## Working rules for this repo
- Keep filesystem access sandboxed to the job workspace.
- Prefer small service-level changes over endpoint redesigns; the API contract is already outlined by `/chat`, `/jobs`, and `/health`.
- Preserve backend portability by routing model access through the shared Anthropic client helper.
- Persist job state after each meaningful agent step so polling endpoints stay useful.

## Common rules and skills source map
- Common repo rules folder: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/.github/instructions/common/`
- Common repo skills folder: `/home/runner/work/fastapi-anthropic-fs-agent/fastapi-anthropic-fs-agent/.github/skills/`
- These folders are not present in the current repository snapshot; add shared instructions and reusable skills there if the repo adopts them later.

## Validation
- Dependency install: `python -m pip install -r requirements.txt`
- Syntax/import check used in this repo: `ANTHROPIC_API_KEY=dummy python -m compileall app main.py`
