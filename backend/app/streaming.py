import asyncio
import json
import logging
import threading

from collections.abc import Callable

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.pipeline.job import PipelineJob
from app.services.ingest import set_ingest_cancel_event

logger = logging.getLogger(__name__)


def stream_sync_job(
    job,
    request: Request,
    job_name: str = "pipeline",
    on_finished: Callable[[], None] | None = None,
) -> StreamingResponse:
    cancel_event = threading.Event()
    pipeline_job = PipelineJob(job_name, cancel_event)

    async def generate():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        async def run_job() -> None:
            set_ingest_cancel_event(pipeline_job.cancel_event)
            try:
                result = await asyncio.to_thread(job, emit, pipeline_job.cancel_event)
                if not pipeline_job.is_cancelled():
                    await queue.put({"type": "complete", "result": result, "job_id": pipeline_job.job_id})
            except InterruptedError as exc:
                await queue.put({"type": "error", "message": str(exc), "job_id": pipeline_job.job_id})
            except Exception as exc:
                logger.exception("Streaming job failed job_id=%s", pipeline_job.job_id)
                await queue.put({"type": "error", "message": str(exc), "job_id": pipeline_job.job_id})
            finally:
                set_ingest_cancel_event(None)

        task = asyncio.create_task(run_job())

        while True:
            if await request.is_disconnected():
                pipeline_job.cancel_event.set()
                from app.services.ollama_client import unload_ollama_model

                asyncio.create_task(unload_ollama_model())
                task.cancel()
                break

            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                if event.get("type") in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                if task.done() and queue.empty():
                    break

        if not task.done():
            pipeline_job.cancel_event.set()
            from app.services.ollama_client import unload_ollama_model

            asyncio.create_task(unload_ollama_model())
        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            if on_finished is not None:
                on_finished()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
