# ── Build stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

LABEL org.opencontainers.image.source="https://github.com/Arkaikus/fastapi-anthropic-fs-agent"
LABEL org.opencontainers.image.description="Anthropic filesystem agent via FastAPI"

# Non-root user for security
RUN useradd --create-home --shell /bin/bash agent
USER agent
WORKDIR /home/agent/app

COPY --from=builder /install /usr/local
COPY --chown=agent:agent . .

# The workspace volume will be mounted here at runtime
RUN mkdir -p /home/agent/app/.workspace

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
