import pytest
from fastapi.testclient import TestClient

from app.deps import pipeline_lock


def test_pipeline_status_idle(client: TestClient):
    pipeline_lock.end_pipeline_job()
    response = client.get("/api/pipeline/status")
    assert response.status_code == 200
    data = response.json()
    assert data["busy"] is False
    assert data["active_job"] is None


def test_pipeline_status_busy(client: TestClient):
    pipeline_lock.end_pipeline_job()
    assert pipeline_lock.try_begin_pipeline_job("ingest")
    try:
        response = client.get("/api/pipeline/status")
        assert response.status_code == 200
        data = response.json()
        assert data["busy"] is True
        assert data["active_job"] == "ingest"
    finally:
        pipeline_lock.end_pipeline_job()
