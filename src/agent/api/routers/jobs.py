from fastapi import APIRouter, HTTPException, Depends
from ..dependencies import get_job_repository
from ...domain.models import Job
from ...domain.schemas import JobEventsResponse, JobSummary
from ...repositories.job_repository import AbstractJobRepository

router = APIRouter()


@router.get("", response_model=list[JobSummary])
async def list_jobs(
    repo: AbstractJobRepository = Depends(get_job_repository),
):
    """List all jobs with summary info (no event log)."""
    return [
        JobSummary(
            id=j.id,
            status=j.status,
            prompt=j.prompt[:80],
            created_at=j.created_at,
        )
        for j in repo.list_all()
    ]


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    repo: AbstractJobRepository = Depends(get_job_repository),
):
    """Return full job state including event log and final result."""
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/events", response_model=JobEventsResponse)
async def get_job_events(
    job_id: str,
    repo: AbstractJobRepository = Depends(get_job_repository),
):
    """Return only the event log for lightweight polling."""
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobEventsResponse(
        job_id=job.id,
        status=job.status,
        events=job.events,
    )
