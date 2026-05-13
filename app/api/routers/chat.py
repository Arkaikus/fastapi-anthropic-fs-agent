from fastapi import APIRouter, BackgroundTasks, Depends
from app.api.dependencies import get_agent_service, get_job_repository
from app.core.config import settings
from app.domain.models import Job
from app.domain.schemas import ChatRequest, JobCreatedResponse
from app.repositories.job_repository import AbstractJobRepository
from app.services.agent_service import AgentService
from pathlib import Path

router = APIRouter()


@router.post("", response_model=JobCreatedResponse, status_code=202)
async def enqueue_chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    repo: AbstractJobRepository = Depends(get_job_repository),
    agent_service: AgentService = Depends(get_agent_service),
):
    """
    Enqueue a new agent job. Returns HTTP 202 immediately with a job_id.
    The agent runs in the background; poll GET /jobs/{job_id} for results.
    """
    base_dir = str(Path(req.base_dir or settings.default_base_dir).resolve())
    job = Job(prompt=req.prompt, base_dir=base_dir)
    repo.save(job)
    background_tasks.add_task(agent_service.run, job)
    return JobCreatedResponse(
        job_id=job.id,
        status=job.status,
        message=f"Job enqueued. Poll /jobs/{job.id} for updates.",
    )
