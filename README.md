# fastapi-anthropic-fs-agent

A FastAPI proof of concept that runs a repo-owned Anthropic agent loop with filesystem tools, async job tracking, and backend switching between Anthropic-hosted models and Ollama.

## Project Structure

```
main.py                          # Compatibility launcher
src/agent/
├── api/
│   ├── dependencies.py          # FastAPI DI providers
│   └── routers/
│       ├── chat.py              # POST /chat  → 202 + job_id
│       └── jobs.py              # GET /jobs, /jobs/{id}, /jobs/{id}/events
├── core/
│   ├── config.py                # pydantic-settings (env vars)
│   ├── anthropic_client.py      # Singleton async Anthropic client (cloud or Ollama)
│   └── logging.py
├── domain/
│   ├── models.py                # Job, AgentEvent, enums
│   └── schemas.py               # API request/response schemas
├── repositories/
│   └── job_repository.py        # Abstract port + InMemory adapter
├── services/
│   ├── agent_service.py         # Anthropic Messages API loop + tool orchestration
│   ├── event_listener.py        # Anthropic responses → AgentEvent
│   ├── rag_service.py           # Prompt-focused RAG + workspace exploration bootstrap
│   └── tool_factory.py          # Repo-owned filesystem tool registry
├── factory.py                   # create_app()
└── main.py                      # FastAPI app entrypoint
Dockerfile
compose.yaml
.env.example
requirements.txt
```

## Quick Start (local)

```bash
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY
mkdir -p .workspace
uv sync
uv run uvicorn agent.main:app --reload --reload-dir src
```

## Docker Compose — Anthropic Cloud

```bash
cp .env.example .env
# set ANTHROPIC_API_KEY, leave ANTHROPIC_BASE_URL blank
docker compose --profile cloud up --build
```

## Docker Compose — Ollama (local LLM)

```bash
cp .env.example .env
# In .env set:
#   ANTHROPIC_API_KEY=ollama
#   ANTHROPIC_BASE_URL=http://ollama:11434/v1
#   MODEL=llama3.1

docker compose --profile ollama up --build
# Pull your model once Ollama is up:
docker compose exec ollama ollama pull llama3.1
```

Agent file output lands in `.workspace/` on your host machine (bind-mounted).

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Enqueue a job → `{ job_id, status }` (HTTP 202) |
| `GET` | `/jobs` | List all jobs (summaries) |
| `GET` | `/jobs/{id}` | Full job detail + result |
| `GET` | `/jobs/{id}/events` | Lightweight event log polling |
| `GET` | `/health` | Health check |

## Backend switching

| Var | Cloud | Ollama |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | `ollama` |
| `ANTHROPIC_BASE_URL` | _(blank)_ | `http://ollama:11434/v1` |
| `MODEL` | `claude-opus-4-5` | `llama3.1` |

No code changes are needed to switch backends — the same Anthropic client is configured through `.env` and can target Anthropic cloud or an Ollama-compatible base URL.

## Agent context priming (RAG + exploration)

Before the first model turn, the API can precompute focused workspace context:
- RAG retrieval over local workspace text files (via ChromaDB)
- Prompt-focused exploration hints (top-level entries + likely relevant files)

Environment knobs:
- `RAG_ENABLED` (default `true`)
- `RAG_MAX_FILES` (default `80`)
- `RAG_MAX_FILE_CHARS` (default `4000`)
- `RAG_QUERY_RESULTS` (default `5`)
- `CHROMA_HOST` (default `localhost`, set to `chromadb` in Docker Compose)
- `CHROMA_PORT` (default `8000`)

Startup preindexing (optional):

The app can optionally schedule background RAG indexing at FastAPI startup to avoid first-request latency. These settings are opt-in and disabled by default.

New env vars:
- `RAG_PREINDEX_ENABLED=false` — set to `true` to enable startup preindex scheduling.
- `RAG_PREINDEX_PATHS=".workspace,examples"` — comma-separated list of paths to prewarm.
- `RAG_BACKGROUND_WORKERS=1` — number of concurrent background index workers.

Example `.env` entries to enable preindexing for the default workspace:

```
RAG_PREINDEX_ENABLED=true
RAG_PREINDEX_PATHS=.workspace
RAG_BACKGROUND_WORKERS=2
```

If `chromadb` is unavailable or unreachable, RAG remains gracefully disabled and the agent runs without retrieval augmentation.
