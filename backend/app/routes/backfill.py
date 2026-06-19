import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_api_key
from app.schemas import (
    BackfillStatusResponse,
    EnrichBackfillResult,
    ObsidianBackfillResult,
    ObsidianDigestResponse,
    ObsidianMigrateResult,
    ObsidianMocsResult,
)
from app.services.hype_backfill import backfill_missing_hype
from app.services.ingest import (
    enrich_missing_items,
    get_backfill_status,
    re_enrich_legacy_items,
)
from app.services.obsidian_backfill import backfill_obsidian_exports
from app.services.obsidian_digest import generate_weekly_digest
from app.services.obsidian_vault import (
    ensure_moc_stubs,
    migrate_legacy_vault_layout,
    organize_loose_vault_notes,
)
from app.deps.pipeline_guard import guard_pipeline_stream
from app.deps.pipeline_lock import end_pipeline_job
from app.streaming import stream_sync_job

router = APIRouter(tags=["backfill"])


@router.get("/api/backfill/status", response_model=BackfillStatusResponse)
def backfill_status(db: Session = Depends(get_db)):
    return BackfillStatusResponse(**get_backfill_status(db))


@router.post("/api/backfill/obsidian", response_model=ObsidianBackfillResult, dependencies=[Depends(require_api_key)])
async def obsidian_backfill(db: Session = Depends(get_db)):
    return await asyncio.to_thread(backfill_obsidian_exports, db)


@router.post("/api/backfill/obsidian/mocs", response_model=ObsidianMocsResult, dependencies=[Depends(require_api_key)])
async def obsidian_mocs_backfill():
    try:
        result = await asyncio.to_thread(ensure_moc_stubs)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ObsidianMocsResult(**result)


@router.post("/api/backfill/obsidian/digest", response_model=ObsidianDigestResponse, dependencies=[Depends(require_api_key)])
async def obsidian_digest_backfill(db: Session = Depends(get_db)):
    try:
        path = await asyncio.to_thread(generate_weekly_digest, db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ObsidianDigestResponse(created=True, path=path)


@router.post("/api/backfill/obsidian/organize", response_model=ObsidianMigrateResult, dependencies=[Depends(require_api_key)])
async def obsidian_organize_backfill(db: Session = Depends(get_db)):
    try:
        result = organize_loose_vault_notes(db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ObsidianMigrateResult(
        migrated=0,
        skipped=result.get("skipped", 0),
        errors=result.get("errors", []),
        organized=result.get("organized", 0),
    )


@router.post("/api/backfill/obsidian/migrate", response_model=ObsidianMigrateResult, dependencies=[Depends(require_api_key)])
async def obsidian_migrate_backfill(db: Session = Depends(get_db)):
    try:
        result = await asyncio.to_thread(migrate_legacy_vault_layout, db)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ObsidianMigrateResult(**result)


@router.post("/api/backfill/re-enrich", response_model=EnrichBackfillResult, dependencies=[Depends(require_api_key)])
async def re_enrich_backfill(
    limit: int = Query(default=1, ge=1, le=10),
    db: Session = Depends(get_db),
):
    return await asyncio.to_thread(re_enrich_legacy_items, db, limit)


@router.post("/api/backfill/re-enrich/stream", dependencies=[Depends(require_api_key)])
async def re_enrich_backfill_stream(
    request: Request,
    limit: int = Query(default=1, ge=1, le=10),
    db: Session = Depends(get_db),
):
    guard_pipeline_stream("re-enrich")

    def job(emit, cancel_event=None):
        try:
            return re_enrich_legacy_items(db, limit, on_progress=emit)
        finally:
            end_pipeline_job()

    return stream_sync_job(job, request, job_name="re-enrich", on_finished=end_pipeline_job)


@router.post("/api/enrich-backfill", response_model=EnrichBackfillResult, dependencies=[Depends(require_api_key)])
async def enrich_backfill(
    limit: int = Query(default=1, ge=1, le=10),
    db: Session = Depends(get_db),
):
    return await asyncio.to_thread(enrich_missing_items, db, limit)


@router.post("/api/enrich-backfill/stream", dependencies=[Depends(require_api_key)])
async def enrich_backfill_stream(
    request: Request,
    limit: int = Query(default=1, ge=1, le=10),
    db: Session = Depends(get_db),
):
    guard_pipeline_stream("enrich-backfill")

    def job(emit, cancel_event=None):
        try:
            return enrich_missing_items(db, limit, on_progress=emit)
        finally:
            end_pipeline_job()

    return stream_sync_job(job, request, job_name="enrich-backfill", on_finished=end_pipeline_job)
