# fastapi-anthropic-fs-agent

A FastAPI proof of concept that runs a repo-owned Anthropic agent loop with filesystem tools, async job tracking, and backend switching between Anthropic-hosted models and Ollama.

## Project Structure

```
app/
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
factory.py                       # create_app()
main.py                          # Entrypoint
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
pip install -r requirements.txt
uvicorn main:app --reload
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
