from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.deps import pipeline_lock
from app.deps.pipeline_guard import guard_pipeline_stream


def test_pipeline_lock_module():
    pipeline_lock.end_pipeline_job()
    assert pipeline_lock.try_begin_pipeline_job("ingest")
    assert pipeline_lock.active_pipeline_job() == "ingest"
    assert not pipeline_lock.try_begin_pipeline_job("export")
    pipeline_lock.end_pipeline_job()
    assert pipeline_lock.try_begin_pipeline_job("obsidian-export")
    pipeline_lock.end_pipeline_job()
    assert pipeline_lock.active_pipeline_job() is None


def _raise_locked(*_args, **_kwargs):
    raise HTTPException(status_code=409, detail="locked")


def test_ingest_routes_return_409_when_locked(client: TestClient):
    with patch("app.routes.ingest.guard_pipeline_stream", side_effect=_raise_locked):
        stream = client.post("/api/ingest/stream")
        assert stream.status_code == 409

        sync = client.post("/api/ingest")
        assert sync.status_code == 409


def test_guard_pipeline_stream_message():
    pipeline_lock.end_pipeline_job()
    guard_pipeline_stream("ingest")
    try:
        guard_pipeline_stream("export")
        assert False, "expected HTTPException"
    except HTTPException as exc:
        assert exc.status_code == 409
        assert "ingest" in exc.detail
    finally:
        pipeline_lock.end_pipeline_job()
