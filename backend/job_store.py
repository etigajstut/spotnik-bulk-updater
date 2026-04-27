import uuid
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


# In-memory store — works reliably on monday-code since the process is persistent.
# For multi-instance scaling, swap with monday-code Storage API using a per-request
# session token (x_monday_access_token) passed from the frontend.
_jobs: dict = {}


async def create_job(
    board_id: int,
    column_id: str,
    new_value: str,
    filter: Optional[dict] = None,
    total_hint: Optional[int] = None,
) -> dict:
    job = {
        "id": str(uuid.uuid4()),
        "status": JobStatus.PENDING,
        "board_id": board_id,
        "column_id": column_id,
        "new_value": new_value,
        "filter": filter,
        "total": total_hint or 0,
        "processed": 0,
        "failed": 0,
        "cancel_requested": False,
        "message": "",
    }
    _jobs[job["id"]] = job
    return job


async def get_job(job_id: str) -> Optional[dict]:
    return _jobs.get(job_id)


async def update_job(job_id: str, **kwargs) -> None:
    job = _jobs.get(job_id)
    if not job:
        return
    job.update(kwargs)
