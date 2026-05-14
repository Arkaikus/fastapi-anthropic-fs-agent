# AGENTS.md

## Purpose
- This repository exposes a FastAPI API that schedules filesystem-oriented agent jobs.
- The active agent implementation lives in the application codebase and uses the Anthropic Messages API directly instead of Claude CLI or `claude_agent_sdk`.
- Backend selection is configuration-driven through `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, and `MODEL`, which allows the same loop to target Anthropic-hosted models or an Ollama endpoint.

## Source map
- Entrypoint: `main.py`
- App factory and routing: `app/factory.py`
- HTTP endpoints: `app/api/routers/`
- Agent loop orchestration: `app/services/agent_service.py`
- Tool registry and sandboxed filesystem operations: `app/services/tool_factory.py`
- Job/event models: `app/domain/models.py`
- Repository abstraction: `app/repositories/job_repository.py`
- Runtime configuration and Anthropic client wiring: `app/core/`

## Working rules for this repo
- Keep filesystem access sandboxed to the job workspace.
- Prefer small service-level changes over endpoint redesigns; the API contract is already outlined by `/chat`, `/jobs`, and `/health`.
- Preserve backend portability by routing model access through the shared Anthropic client helper.
- Persist job state after each meaningful agent step so polling endpoints stay useful.

## Common rules and skills source map
- Common repo rules folder: `.github/instructions/common/`
- Common repo skills folder: `.github/skills/`
- These folders are not present in the current repository snapshot; add shared instructions and reusable skills there if the repo adopts them later.

## Validation
- Dependency install: `python -m pip install -r requirements.txt`
- Syntax/import check used in this repo: `ANTHROPIC_API_KEY=dummy python -m compileall app main.py`

## RAG preindexing (startup)

This repository supports optional RAG preindexing at application startup so that workspace indexing does not block the first agent request.

- Behavior: when enabled the application will schedule background indexing tasks for configured workspace paths at FastAPI startup. Indexing runs in background workers and uses a thread executor for file I/O and Chroma client calls so the event loop is not blocked.
- Chromadb dependency: if `chromadb` is not installed or reachable, RAG and preindexing are skipped and the agent continues to operate without RAG.

Config / env vars (new):

- `RAG_PREINDEX_ENABLED` (default: `false`) — enable startup preindex scheduling.
- `RAG_PREINDEX_PATHS` (default: empty) — comma-separated list of filesystem paths to prewarm (e.g. `.workspace,examples`).
- `RAG_BACKGROUND_WORKERS` (default: `1`) — number of concurrent background indexing workers.

Notes:

- Preindexing is opt-in and disabled by default to avoid unexpected startup work.
- The RAG cache is still maintained per-workspace; startup preindexing only improves first-request latency by doing index work in the background.
- For large repositories, tune `RAG_BACKGROUND_WORKERS` and `RAG_MAX_FILES` to control memory and CPU usage.

