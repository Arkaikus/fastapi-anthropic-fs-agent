from functools import lru_cache
from fastapi import Depends
from ..repositories.job_repository import AbstractJobRepository, InMemoryJobRepository
from ..services.agent_service import AgentService
from ..core.rag import get_rag_service


@lru_cache(maxsize=1)
def get_job_repository() -> AbstractJobRepository:
    """Singleton in-memory repo. Replace with RedisJobRepository for production."""
    return InMemoryJobRepository()


def get_agent_service(
    repo: AbstractJobRepository = Depends(get_job_repository),
) -> AgentService:
    rag = get_rag_service()
    return AgentService(repo=repo, rag=rag)
