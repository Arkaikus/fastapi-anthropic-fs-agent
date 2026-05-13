from fastapi import FastAPI
from app.api.routers import chat, jobs
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Filesystem Agent API",
        version="3.0.0",
        description="Anthropic agent with filesystem tools, job queue, and event tracking.",
        docs_url="/docs" if settings.app_env != "production" else None,
    )

    app.include_router(chat.router, prefix="/chat", tags=["Chat"])
    app.include_router(jobs.router, prefix="/jobs", tags=["Jobs"])

    @app.get("/health", tags=["Health"])
    async def health():
        return {"status": "ok", "env": settings.app_env}

    return app
