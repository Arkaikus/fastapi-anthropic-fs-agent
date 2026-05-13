from functools import lru_cache
from fastapi import Depends
from app.repositories.job_repository import AbstractJobRepository, InMemoryJobRepository
from app.services.agent_service import AgentService


@lru_cache(maxsize=1)
def get_job_repository() -> AbstractJobRepository:
    """Singleton in-memory repo. Replace with RedisJobRepository for production."""
    return InMemoryJobRepository()


def get_agent_service(
    repo: AbstractJobRepository = Depends(get_job_repository),
) -> AgentService:
    return AgentService(repo=repo)
