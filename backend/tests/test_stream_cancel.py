import json
import threading
from unittest.mock import AsyncMock, patch

import pytest
from starlette.responses import StreamingResponse

from app.streaming import stream_sync_job


class _FakeRequest:
    def __init__(self, disconnect_after: int = 0):
        self._calls = 0
        self._disconnect_after = disconnect_after

    async def is_disconnected(self) -> bool:
        self._calls += 1
        return self._disconnect_after > 0 and self._calls >= self._disconnect_after


def _parse_sse_events(chunks: list[str]) -> list[dict]:
    events: list[dict] = []
    for block in "".join(chunks).strip().split("\n\n"):
        for line in block.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


@pytest.mark.asyncio
async def test_stream_sync_job_completes_with_result():
    def job(emit, cancel_event=None):
        emit({"type": "step", "step_id": "fetch", "status": "done"})
        return {"saved": 1}

    request = _FakeRequest()
    response = stream_sync_job(job, request, job_name="test-ingest")
    assert isinstance(response, StreamingResponse)

    chunks: list[str] = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    events = _parse_sse_events(chunks)
    assert events[-1]["type"] == "complete"
    assert events[-1]["result"]["saved"] == 1
    assert "job_id" in events[-1]


@pytest.mark.asyncio
async def test_stream_sync_job_sets_cancel_on_disconnect():
    cancel_events: list[threading.Event] = []

    def job(emit, cancel_event=None):
        from app.services.ingest import _ingest_cancel_event

        if _ingest_cancel_event is not None:
            cancel_events.append(_ingest_cancel_event)
        import time

        time.sleep(1.5)
        return {"saved": 0}

    request = _FakeRequest(disconnect_after=2)
    response = stream_sync_job(job, request, job_name="test-cancel")

    with patch("app.services.ollama_client.unload_ollama_model", new_callable=AsyncMock):
        async for _chunk in response.body_iterator:
            pass

    assert cancel_events
    assert cancel_events[0].is_set()
