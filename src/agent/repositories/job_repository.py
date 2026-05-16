from __future__ import annotations
from abc import ABC, abstractmethod
from ..domain.models import Job


class AbstractJobRepository(ABC):
    """Port: defines the contract for job persistence."""

    @abstractmethod
    def save(self, job: Job) -> None: ...

    @abstractmethod
    def get(self, job_id: str) -> Job | None: ...

    @abstractmethod
    def list_all(self) -> list[Job]: ...


class InMemoryJobRepository(AbstractJobRepository):
    """
    Adapter: in-memory implementation.
    Swap for RedisJobRepository or SQLJobRepository without touching services.
    """

    def __init__(self) -> None:
        self._store: dict[str, Job] = {}

    def save(self, job: Job) -> None:
        self._store[job.id] = job

    def get(self, job_id: str) -> Job | None:
        return self._store.get(job_id)

    def list_all(self) -> list[Job]:
        return list(self._store.values())
