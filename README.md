# fastapi-anthropic-fs-agent

A production-ready Anthropic agent exposed via FastAPI with filesystem tools,
async job queue, event tracking, and Docker Compose deployment.

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
│   ├── anthropic_client.py      # Singleton Anthropic client (cloud or Ollama)
│   └── logging.py
├── domain/
│   ├── models.py                # Job, AgentEvent, enums
│   └── schemas.py               # API request/response schemas
├── repositories/
│   └── job_repository.py        # Abstract port + InMemory adapter
├── services/
│   ├── agent_service.py         # Agentic loop orchestration
│   ├── event_listener.py        # StreamEvent → AgentEvent
│   └── tool_factory.py          # @tool filesystem factory
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

No code changes are needed to switch backends — only `.env` values.
