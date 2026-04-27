import json
import uuid
from typing import Optional
from enum import Enum

import monday_code
from monday_code.models.json_data_contract import JsonDataContract

STORAGE_HOST = "http://localhost:59999"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


def _client():
    config = monday_code.Configuration(host=STORAGE_HOST)
    return monday_code.ApiClient(config)


async def create_job(
    board_id: int,
    column_id: str,
    new_value: str,
    filter: Optional[dict] = None,
    total_hint: Optional[int] = None,
    session_token: Optional[str] = None,
) -> dict:
    """Create a new job. Persists to monday-code Storage if session_token is available."""
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
        "session_token": session_token,  # stored so background worker can use it
    }

    if session_token:
        _token_cache[job["id"]] = session_token
        try:
            async with _client() as api_client:
                api = monday_code.StorageApi(api_client)
                await api.upsert_by_key_from_storage(
                    key=f"job:{job['id']}",
                    x_monday_access_token=session_token,
                    json_data_contract=JsonDataContract(value=json.dumps(_serializable(job))),
                )
            print(f"Job {job['id']} persisted to monday-code Storage.")
        except Exception as e:
            print(f"Storage API unavailable, falling back to in-memory: {e}")
            _jobs[job["id"]] = job
    else:
        # No session token — running locally or outside monday.com
        _jobs[job["id"]] = job

    return job


async def get_job(job_id: str) -> Optional[dict]:
    """Read job — from Storage if token available, otherwise from memory."""
    # Try in-memory first (fastest)
    if job_id in _jobs:
        return _jobs[job_id]

    # Try Storage API using the token stored in the job
    # We don't have the token here yet — this path is for when job was stored in Storage
    # We'll use a cached token lookup
    token = _token_cache.get(job_id)
    if token:
        try:
            async with _client() as api_client:
                api = monday_code.StorageApi(api_client)
                response = await api.get_by_key_from_storage(
                    key=f"job:{job_id}",
                    x_monday_access_token=token,
                )
                if response and response.value:
                    return json.loads(response.value)
        except Exception as e:
            print(f"Storage get failed: {e}")

    return None


async def update_job(job_id: str, **kwargs) -> None:
    """Update job — in Storage if token available, otherwise in memory."""
    # In-memory path
    if job_id in _jobs:
        _jobs[job_id].update(kwargs)
        return

    # Storage API path
    token = _token_cache.get(job_id)
    if not token:
        return

    job = await get_job(job_id)
    if not job:
        return
    job.update(kwargs)

    try:
        async with _client() as api_client:
            api = monday_code.StorageApi(api_client)
            await api.upsert_by_key_from_storage(
                key=f"job:{job_id}",
                x_monday_access_token=token,
                json_data_contract=JsonDataContract(value=json.dumps(_serializable(job))),
            )
    except Exception as e:
        print(f"Storage update failed: {e}")


# ── Helpers ───────────────────────────────────────────────────────────────────

# Fallback in-memory store (used when running locally or when Storage API fails)
_jobs: dict = {}

# Maps job_id → session_token so get_job/update_job can authenticate Storage calls
_token_cache: dict = {}


def _register_token(job_id: str, token: str):
    """Cache the session token for a job so background tasks can use it."""
    _token_cache[job_id] = token


def _serializable(job: dict) -> dict:
    """Convert job dict to JSON-serializable form (enum values → strings)."""
    return {k: (v.value if isinstance(v, JobStatus) else v) for k, v in job.items()}
