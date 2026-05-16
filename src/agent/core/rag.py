from __future__ import annotations

from functools import lru_cache

from ..services.rag_service import RagService


@lru_cache(maxsize=1)
def get_rag_service() -> RagService:
    """Return a singleton RagService for the application."""
    return RagService()
