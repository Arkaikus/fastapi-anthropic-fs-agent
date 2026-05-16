dev:
    uv run uvicorn agent.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src

format:
    uv run ruff format . --line-length 190

lint:
    uv run ruff check .
