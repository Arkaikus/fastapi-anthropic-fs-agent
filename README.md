# fastapi-anthropic-fs-agent

A production-ready Anthropic agent exposed via FastAPI with filesystem tools, async job queue, and structured event tracking.

## Project Structure

```
app/
├── api/
│   ├── __init__.py
│   ├── dependencies.py       # FastAPI DI providers
│   └── routers/
│       ├── __init__.py
│       ├── jobs.py           # Job CRUD endpoints
│       └── chat.py           # POST /chat enqueue endpoint
├── core/
│   ├── __init__.py
│   ├── config.py             # Settings via pydantic-settings
│   └── logging.py            # Structured logging setup
├── domain/
│   ├── __init__.py
│   ├── models.py             # Job, AgentEvent, enums
│   └── schemas.py            # Request/response Pydantic schemas
├── repositories/
│   ├── __init__.py
│   └── job_repository.py     # Abstract + in-memory implementation
├── services/
│   ├── __init__.py
│   ├── agent_service.py      # Agentic loop orchestration
│   ├── event_listener.py     # StreamEvent → AgentEvent translation
│   └── tool_factory.py       # @tool filesystem tools factory
main.py                       # App entrypoint
.env.example
requirements.txt
```

## Quick Start

```bash
cp .env.example .env
# fill in ANTHROPIC_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload
```

## Usage

```bash
# Enqueue a job
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"prompt": "List all files then create hello.txt", "base_dir": "/tmp"}'
# → { "job_id": "uuid", "status": "pending" }

# Poll status + events
curl http://localhost:8000/jobs/{job_id}/events

# Get full result
curl http://localhost:8000/jobs/{job_id}
```
