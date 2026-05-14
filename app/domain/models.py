from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class EventKind(str, Enum):
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TEXT_DELTA = "text_delta"
    AGENT_INFO = "info"
    ERROR = "error"


class AgentEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    kind: EventKind
    detail: str


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    status: JobStatus = JobStatus.PENDING
    prompt: str
    base_dir: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    events: list[AgentEvent] = Field(default_factory=list)
    result: str | None = None
    error: str | None = None

    def log(self, kind: EventKind, detail: str) -> None:
        self.events.append(AgentEvent(kind=kind, detail=detail))
        self.updated_at = datetime.now(timezone.utc).isoformat()
