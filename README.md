# Spotnik Bulk Status Updater

A monday.com app that allows users to perform bulk status updates on board items at scale.

## Features

- Select any board and status column from your monday.com account
- Filter items by any column value before updating
- Preview how many items will be affected before starting
- Real-time progress bar during bulk update
- Handles thousands of items reliably

## Architecture

### System diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND  (React + Vite)                      │
│                                                                   │
│  ┌─────────────────────────┐   ┌──────────────────────────────┐ │
│  │   ConfigurationPanel    │   │     ProgressIndicator        │ │
│  │                         │   │                              │ │
│  │  • Board selector       │   │  • Polls GET /jobs/:id       │ │
│  │  • Column selector      │   │    every 1 second            │ │
│  │    (status only active) │   │  • Shows progress bar        │ │
│  │  • Filter (optional)    │   │  • Shows processed / total   │ │
│  │  • Preview item count   │   │  • Shows failed count        │ │
│  │  • New value selector   │   │  • Cancel button             │ │
│  │  • Start button         │   │                              │ │
│  └────────────┬────────────┘   └──────────────┬───────────────┘ │
│               │                               │                  │
│               └──────────────┬────────────────┘                  │
│                          api.js (axios)                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND  (FastAPI)                            │
│                                                                   │
│  REST Endpoints                                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  GET  /boards                 → list boards              │    │
│  │  GET  /boards/:id/columns     → list columns             │    │
│  │  POST /preview-count          → count matching items     │    │
│  │  POST /jobs                   → create job, return id    │    │
│  │  GET  /jobs/:id               → get job status           │    │
│  │  POST /jobs/:id/cancel        → request cancellation     │    │
│  └────────────────────────┬────────────────────────────────┘    │
│                           │                                       │
│              ┌────────────┴────────────┐                         │
│              ▼                         ▼                         │
│  ┌───────────────────┐    ┌───────────────────────────────────┐  │
│  │    Job Store      │    │       Background Worker           │  │
│  │  (in-memory dict) │◄──►│       run_bulk_update()          │  │
│  │                   │    │                                   │  │
│  │  • job_id         │    │  1. Fetch page 1 (500 items)      │  │
│  │  • status         │    │  2. Split into 40-item batches    │  │
│  │  • total          │    │  3. Run 2 batches in parallel     │  │
│  │  • processed      │    │  4. Pipeline: fetch next page     │  │
│  │  • failed         │    │     while updating current        │  │
│  │  • cancel flag    │    │  5. Retry failed batches (3x)     │  │
│  └───────────────────┘    │  6. Repeat until all pages done   │  │
│                           └──────────────┬────────────────────┘  │
│                                          │                        │
│                              monday_client.py                     │
└──────────────────────────────────────────┬──────────────────────┘
                                           │ GraphQL (HTTPS)
                                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                   monday.com GraphQL API                         │
│                                                                   │
│  boards()                    → fetch boards & columns            │
│  items_page()                → first page, 500 items + cursor    │
│  next_items_page()           → subsequent pages via cursor       │
│  change_simple_column_value()→ batch update (40 aliases/request) │
│                                                                   │
│  Rate limits handled:                                            │
│  • HTTP 429        → retry after Retry-After header              │
│  • Complexity limit → retry after reset_in_x_seconds             │
└─────────────────────────────────────────────────────────────────┘
```

### High-volume update approach

The core challenge is updating thousands of items without hitting monday.com's API rate limits or timing out.

The solution is a **chunked async processing loop**:

1. When the user clicks "Start", the backend creates a job record immediately and returns a `job_id` to the frontend — the HTTP request returns in milliseconds.
2. A background task starts processing in the background.
3. Items are fetched in pages of 500 using cursor-based pagination (`items_page` + `next_items_page`).
4. Each page is split into batches of 40 items, each batch sent as a single aliased GraphQL mutation.
5. An `asyncio.Semaphore(2)` allows up to 2 batches to run in parallel — enough to roughly double throughput without triggering monday's HTTP 429 rate limits.
6. Progress is updated in memory after each batch.
7. The frontend polls `GET /jobs/{id}` every second to show real-time progress.

### GraphQL optimizations

- **Batching**: 40 mutations are sent in a single aliased GraphQL request, reducing API calls dramatically compared to one mutation per item.
- **Cursor pagination**: Items are fetched page by page using cursors, avoiding memory issues with large boards.
- **Minimal fields**: Item queries only request `id` — no unnecessary data transferred.
- **Complexity tracking**: The `complexity` node is included in mutations to monitor the API budget. If the budget is exhausted, the client sleeps for the required reset time before retrying.
- **Adaptive retry**: GraphQL complexity errors and HTTP 429 responses are both caught and retried automatically — complexity errors use `reset_in_x_seconds` from the error response, HTTP 429 uses the `Retry-After` header.
- **Per-batch retry**: Each batch retries up to 3 times with exponential backoff (10s, 20s, 40s) before being counted as failed.
- **Filter push-down**: Filtering is done server-side using `query_params.rules` in `items_page`, not client-side — so only matching items are fetched and updated.

### Error handling

- Each batch is wrapped in try/except — a single failed batch records the error and moves on without stopping the job.
- Network errors and HTTP errors are caught and surfaced to the job status.
- The cancel endpoint sets a flag that the worker checks between pages.

### Known limitations & scaling notes

- **Job state is stored in-memory.** If the server restarts mid-job, the job is lost. For production, swap the in-memory store for monday-code Storage, SQLite, or Redis.
- Multiple server instances would not share job state. A shared storage backend would be needed for horizontal scaling.
- For higher scale, the in-memory job store and asyncio background tasks could be replaced with Redis + Celery workers without changing the core chunking logic. The semaphore-based concurrency control would map directly to Celery's worker concurrency settings.
- The current solution was intentionally kept simple — no external infrastructure, single process, easy to deploy on monday-code. This is the right tradeoff for this use case.

## Tech stack

- **Frontend**: React + Vite + monday-sdk-js + monday Vibe (monday-ui-react-core)
- **Backend**: Python + FastAPI + httpx
- **API**: monday.com GraphQL API v2

## How to run locally

### Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn httpx python-dotenv
```

Create a `.env` file:
```
MONDAY_API_KEY=your_key_here
```

Run:
```bash
uvicorn main:app --reload --port 8001
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5174`

## How I used AI tools

I used **Claude (Anthropic)** as a consulting tool throughout the process — asking questions, validating decisions, and getting explanations when I needed them.

Areas where I consulted Claude:
- Understanding monday.com API concepts (complexity points, cursor pagination, label indexes)
- Debugging the monday-ui-react-core `Dropdown` overflow clipping issue (`insideOverflowContainer` prop)
- Discussing trade-offs between approaches (serial vs parallel batch processing, in-memory vs persistent job storage)
- Explaining error patterns when diagnosing the HTTP 429 rate limit bug


