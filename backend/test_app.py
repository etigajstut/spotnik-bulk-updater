import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from job_store import JobStore, JobStatus

# ── Job Store Tests ──────────────────────────────────

def test_create_job():
    store = JobStore()
    job = store.create_job(
        board_id=123,
        column_id="status",
        new_value="Done"
    )
    assert job["id"] is not None
    assert job["board_id"] == 123
    assert job["column_id"] == "status"
    assert job["new_value"] == "Done"
    assert job["status"] == JobStatus.QUEUED
    assert job["processed"] == 0
    assert job["failed"] == 0
    assert job["total"] == 0
    assert job["cancel_requested"] == False

def test_get_job():
    store = JobStore()
    job = store.create_job(board_id=123, column_id="status", new_value="Done")
    fetched = store.get_job(job["id"])
    assert fetched["id"] == job["id"]

def test_get_job_not_found():
    store = JobStore()
    result = store.get_job("nonexistent-id")
    assert result is None

def test_update_job():
    store = JobStore()
    job = store.create_job(board_id=123, column_id="status", new_value="Done")
    updated = store.update_job(job["id"], status=JobStatus.RUNNING, processed=25)
    assert updated["status"] == JobStatus.RUNNING
    assert updated["processed"] == 25

def test_update_job_not_found():
    store = JobStore()
    result = store.update_job("nonexistent-id", status=JobStatus.RUNNING)
    assert result is None

def test_cancel_job():
    store = JobStore()
    job = store.create_job(board_id=123, column_id="status", new_value="Done")
    store.update_job(job["id"], cancel_requested=True)
    fetched = store.get_job(job["id"])
    assert fetched["cancel_requested"] == True

def test_job_with_filter():
    store = JobStore()
    filter = {"column_id": "status", "operator": "any_of", "values": ["7"]}
    job = store.create_job(
        board_id=123,
        column_id="status",
        new_value="Done",
        filter=filter
    )
    assert job["filter"] == filter

# ── API Endpoint Tests ───────────────────────────────

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_get_job_endpoint_not_found():
    response = client.get("/jobs/nonexistent-id")
    assert response.status_code == 404

def test_cancel_job_endpoint_not_found():
    response = client.post("/jobs/nonexistent-id/cancel")
    assert response.status_code == 404

@patch("main.get_boards", new_callable=AsyncMock)
def test_get_boards(mock_get_boards):
    mock_get_boards.return_value = [
        {"id": "123", "name": "Test Board"}
    ]
    response = client.get("/boards")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "Test Board"

@patch("main.get_columns", new_callable=AsyncMock)
def test_get_columns(mock_get_columns):
    mock_get_columns.return_value = [
        {"id": "status", "title": "Status", "type": "status", "settings_str": "{}"}
    ]
    response = client.get("/boards/123/columns")
    assert response.status_code == 200
    assert response.json()[0]["title"] == "Status"

@patch("main.asyncio.create_task")
@patch("main.get_items_page", new_callable=AsyncMock)
def test_start_job(mock_get_items, mock_create_task):
    mock_get_items.return_value = {"items": [], "cursor": None}
    response = client.post("/jobs", json={
        "board_id": 123,
        "column_id": "status",
        "new_value": "Done",
        "filter": None
    })
    assert response.status_code == 200
    assert "job_id" in response.json()

@patch("main.get_items_page", new_callable=AsyncMock)
def test_preview_count_no_filter(mock_get_items):
    mock_get_items.return_value = {"items": [{"id": "1"}, {"id": "2"}], "cursor": None}
    response = client.post("/preview-count", json={
        "board_id": 123,
        "column_id": "status",
        "new_value": "Done",
        "filter": None
    })
    assert response.status_code == 200
    assert response.json()["count"] == 2