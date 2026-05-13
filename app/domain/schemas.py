from pydantic import BaseModel
from app.domain.models import JobStatus, AgentEvent


class ChatRequest(BaseModel):
    prompt: str
    base_dir: str = "."


class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str


class JobEventsResponse(BaseModel):
    job_id: str
    status: JobStatus
    events: list[AgentEvent]


class JobSummary(BaseModel):
    id: str
    status: JobStatus
    prompt: str
    created_at: str
