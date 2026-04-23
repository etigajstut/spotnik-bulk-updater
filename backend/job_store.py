import uuid
from datetime import datetime
from typing import Optional
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class JobStore:
    """In-memory job store. For production, replace with Redis or monday-code Storage."""

    def __init__(self):
        self._jobs = {}

    def create_job(self, board_id: int, column_id: str, new_value: str, filter: Optional[dict] = None) -> dict:
        job_id = str(uuid.uuid4())
        job = {
            "id": job_id,
            "board_id": board_id,
            "column_id": column_id,
            "new_value": new_value,
            "filter": filter,
            "status": JobStatus.QUEUED,
            "total": 0,
            "processed": 0,
            "failed": 0,
            "cancel_requested": False,
            "created_at": datetime.utcnow().isoformat(),
        }
        self._jobs[job_id] = job
        return job

    def get_job(self, job_id: str) -> Optional[dict]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **kwargs) -> Optional[dict]:
        job = self._jobs.get(job_id)
        if not job:
            return None
        job.update(kwargs)
        return job


# Singleton shared across the app
job_store = JobStore()
