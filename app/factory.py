from fastapi import FastAPI
from app.api.routers import chat, jobs
from app.core.config import settings
from app.core.rag import get_rag_service
from app.core.logging import get_logger

logger = get_logger(__name__)


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

    @app.on_event("startup")
    async def _startup_rag():
        if settings.rag_enabled and settings.rag_preindex_enabled and settings.rag_preindex_paths:
            rag = get_rag_service()
            try:
                # start background indexing; do not block startup
                rag.start_background_index(settings.rag_preindex_paths)
                logger.info(
                    "RAG preindex scheduled for %d paths",
                    len(settings.rag_preindex_paths),
                )
            except Exception as exc:
                logger.debug("Failed to schedule RAG preindex: %s", exc)

    @app.on_event("shutdown")
    async def _shutdown_rag():
        rag = get_rag_service()
        try:
            await rag.shutdown()
        except Exception:
            pass

    return app
