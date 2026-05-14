dev:
    uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload --reload-dir app

format:
    uv run ruff format . --line-length 190

lint:
    uv run ruff check .
