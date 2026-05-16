# ── Build stage ───────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_LINK_MODE=copy \
	UV_PYTHON_DOWNLOADS=never

WORKDIR /build
COPY pyproject.toml uv.lock README.md main.py ./
COPY src ./src
RUN uv sync --frozen --no-dev

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

LABEL org.opencontainers.image.source="https://github.com/Arkaikus/fastapi-anthropic-fs-agent"
LABEL org.opencontainers.image.description="Anthropic filesystem agent via FastAPI"

ENV UV_LINK_MODE=copy \
	UV_PYTHON_DOWNLOADS=never \
	PATH="/home/agent/app/.venv/bin:$PATH"

# Non-root user for security
RUN useradd --create-home --shell /bin/bash agent
WORKDIR /home/agent/app

COPY --from=builder --chown=agent:agent /build /home/agent/app

USER agent

# The workspace volume will be mounted here at runtime
RUN mkdir -p /home/agent/app/.workspace

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "agent.main:app", "--host", "0.0.0.0", "--port", "8000"]
