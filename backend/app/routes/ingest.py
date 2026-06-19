import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import get_app_config
from app.database import get_db
from app.deps.pipeline_guard import guard_pipeline_stream
from app.deps.pipeline_lock import end_pipeline_job
from app.deps.auth import require_api_key
from app.schemas import IngestResult, SeedResult
from app.services.ingest import run_ingest
from app.services.seed import seed_demo_articles
from app.streaming import stream_sync_job

router = APIRouter(tags=["ingest"])


@router.post("/api/ingest", response_model=IngestResult, dependencies=[Depends(require_api_key)])
async def trigger_ingest(db: Session = Depends(get_db)):
    guard_pipeline_stream("ingest")
    try:
        return await asyncio.to_thread(run_ingest, db)
    finally:
        end_pipeline_job()


@router.post("/api/ingest/stream", dependencies=[Depends(require_api_key)])
async def trigger_ingest_stream(request: Request, db: Session = Depends(get_db)):
    guard_pipeline_stream("ingest")

    def job(emit, cancel_event):
        try:
            return run_ingest(db, on_progress=emit, cancel_event=cancel_event)
        finally:
            end_pipeline_job()

    return stream_sync_job(job, request, job_name="ingest", on_finished=end_pipeline_job)


@router.post("/api/seed", response_model=SeedResult, dependencies=[Depends(require_api_key)])
async def seed_demo(db: Session = Depends(get_db)):
    if not get_app_config().allow_seed:
        raise HTTPException(status_code=403, detail="Endpoint de seed desabilitado")
    return await asyncio.to_thread(seed_demo_articles, db)
