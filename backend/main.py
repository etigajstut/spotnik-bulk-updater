import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

from job_store import job_store, JobStatus
from monday_client import get_boards, get_columns, get_items_page, update_items_batch

load_dotenv()

app = FastAPI(title="Spotnik Bulk Status Updater")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class StartJobRequest(BaseModel):
    board_id: int
    column_id: str
    new_value: str
    filter: Optional[dict] = None
    total_hint: Optional[int] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/boards")
async def list_boards():
    return await get_boards()


@app.get("/boards/{board_id}/columns")
async def list_columns(board_id: int):
    return await get_columns(board_id)


@app.post("/preview-count")
async def preview_count(req: StartJobRequest):
    """Count items matching the filter before starting the job."""
    try:
        count = 0
        cursor = None
        while True:
            page = await get_items_page(req.board_id, cursor=cursor, filter=req.filter)
            count += len(page["items"])
            cursor = page["cursor"]
            if not cursor:
                break
        return {"count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/jobs")
async def start_job(req: StartJobRequest, background_tasks: BackgroundTasks):
    """Create a job and start processing in the background. Returns job_id immediately."""
    job = job_store.create_job(
        board_id=req.board_id,
        column_id=req.column_id,
        new_value=req.new_value,
        filter=req.filter,
        total_hint=req.total_hint
    )
    background_tasks.add_task(run_bulk_update, job["id"])
    return {"job_id": job["id"]}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job_store.update_job(job_id, cancel_requested=True)
    return {"status": "cancel requested"}


# ── Background Worker ─────────────────────────────────────────────────────────

async def run_bulk_update(job_id: str):
    """
    Processes a bulk update job in the background.

    Flow:
    1. Fetch items in pages of 500 (cursor pagination)
    2. Split each page into batches of 40 items
    3. Run up to 2 batches in parallel (semaphore) to stay within monday's rate limits
    4. Pipeline: fetch the next page while updating the current one
    5. Check for cancellation between pages
    6. Each batch retries up to 3 times on error before giving up
    """
    job = job_store.get_job(job_id)
    board_id = job["board_id"]
    column_id = job["column_id"]
    new_value = job["new_value"]

    job_store.update_job(job_id, status=JobStatus.RUNNING)

    total = 0
    has_total_hint = job["total"] > 0  # total already set from preview count

    # 2 concurrent batches of 40 items — fewest rate limit hits, reliable performance
    semaphore = asyncio.Semaphore(2)

    async def process_batch(batch):
        async with semaphore:
            item_ids = [item["id"] for item in batch]
            for attempt in range(3):
                try:
                    await update_items_batch(board_id, item_ids, column_id, new_value)
                    current = job_store.get_job(job_id)["processed"]
                    job_store.update_job(job_id, processed=current + len(batch))
                    return
                except Exception as e:
                    wait = 10 * (2 ** attempt)  # 10s, 20s, 40s
                    print(f"Batch error (attempt {attempt + 1}/3): {e}. Retrying in {wait}s...")
                    await asyncio.sleep(wait)
            # All 3 attempts failed — move on
            print(f"Batch permanently failed after 3 attempts.")
            current_failed = job_store.get_job(job_id)["failed"]
            job_store.update_job(job_id, failed=current_failed + len(batch))

    async def process_page(items):
        """Update all batches in a page, 2 at a time."""
        batches = [items[i:i + 50] for i in range(0, len(items), 50)]
        await asyncio.gather(*[process_batch(b) for b in batches])

    try:
        # Fetch first page
        page = await get_items_page(board_id, cursor=None, filter=job["filter"])
        page_num = 1
        print(f"Job {job_id} | Page {page_num}: {len(page['items'])} items, cursor={'YES' if page['cursor'] else 'NO'}")

        while True:
            items = page["items"]
            cursor = page["cursor"]

            if not items:
                print(f"Job {job_id} | Page {page_num}: no items, stopping.")
                break

            # Check for cancellation between pages
            if job_store.get_job(job_id)["cancel_requested"]:
                job_store.update_job(job_id, status=JobStatus.CANCELED)
                return

            total += len(items)
            if not has_total_hint:
                job_store.update_job(job_id, total=total)

            if cursor:
                # Pipeline: fetch next page and update current page simultaneously
                _, next_page = await asyncio.gather(
                    process_page(items),
                    get_items_page(board_id, cursor=cursor, filter=job["filter"])
                )
                page_num += 1
                print(f"Job {job_id} | Page {page_num}: {len(next_page['items'])} items, cursor={'YES' if next_page['cursor'] else 'NO'}")
                page = next_page
            else:
                # Last page — just update, no next fetch needed
                await process_page(items)
                break

        job_store.update_job(job_id, status=JobStatus.SUCCEEDED)
        print(f"Job {job_id} completed. {total} items processed.")

    except Exception as e:
        print(f"Job {job_id} failed: {e}")
        job_store.update_job(job_id, status=JobStatus.FAILED)
