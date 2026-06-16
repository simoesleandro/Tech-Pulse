from contextlib import asynccontextmanager
import asyncio
import json
import logging
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.database import Base, SessionLocal, engine, get_db
from app.models import NewsItem, TopicFolder, migrate_sqlite_schema
from app.schemas import (
    BulkNewsDelete,
    BulkNewsResult,
    BulkNewsUpdate,
    EnrichBackfillResult,
    HealthResponse,
    IngestResult,
    NewsItemBookmarkUpdate,
    NewsItemCreate,
    NewsItemFolderUpdate,
    NewsItemReadUpdate,
    NewsItemResponse,
    NewsCountResponse,
    NewsListResponse,
    ObsidianExportRequest,
    ObsidianExportResult,
    ObsidianStatusResponse,
    PipelineConfigResponse,
    PipelineStepResponse,
    SeedResult,
    TopicFolderCreate,
    TopicFolderResponse,
)
from app.services.pipeline_config import (
    BACKFILL_PIPELINE_STEPS,
    INGEST_PIPELINE_STEPS,
    steps_to_dict,
)
from app.services.hype_backfill import backfill_missing_hype
from app.services.ingest import enrich_missing_items, run_ingest, set_ingest_cancel_event
from app.services.obsidian import (
    check_rest_connection,
    export_items_to_obsidian,
    get_obsidian_config,
)
from app.services.seed import seed_demo_articles

logger = logging.getLogger(__name__)

INGEST_INTERVAL_SECONDS = int(os.getenv("INGEST_INTERVAL_SECONDS", "300"))
INGEST_ON_STARTUP = os.getenv("INGEST_ON_STARTUP", "false").lower() == "true"
INGEST_BACKGROUND = os.getenv("INGEST_BACKGROUND", "false").lower() == "true"


def _stream_sync_job(job, request: Request):
    cancel_event = threading.Event()

    async def generate():
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def emit(event: dict) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        async def run_job() -> None:
            set_ingest_cancel_event(cancel_event)
            try:
                result = await asyncio.to_thread(job, emit)
                if not cancel_event.is_set():
                    await queue.put({"type": "complete", "result": result})
            except InterruptedError as exc:
                await queue.put({"type": "error", "message": str(exc)})
            except Exception as exc:
                logger.exception("Streaming job failed")
                await queue.put({"type": "error", "message": str(exc)})
            finally:
                set_ingest_cancel_event(None)

        task = asyncio.create_task(run_job())

        while True:
            if await request.is_disconnected():
                cancel_event.set()
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
            cancel_event.set()
        try:
            await task
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _ingest_loop() -> None:
    while True:
        await asyncio.sleep(INGEST_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            stats = run_ingest(db)
            logger.info("Background ingest finished: %s", stats)
        except Exception:
            logger.exception("Background ingest failed")
        finally:
            db.close()


def _run_startup_ingest() -> None:
    db = SessionLocal()
    try:
        stats = run_ingest(db)
        logger.info("Startup ingest finished: %s", stats)
    except Exception:
        logger.exception("Startup ingest failed")
    finally:
        db.close()


def _run_hype_backfill() -> None:
    db = SessionLocal()
    try:
        updated = backfill_missing_hype(db)
        if updated:
            logger.info("Hype backfill updated %s items on startup", updated)
    except Exception:
        logger.exception("Startup hype backfill failed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    migrate_sqlite_schema()

    asyncio.create_task(asyncio.to_thread(_run_hype_backfill))

    if INGEST_ON_STARTUP:
        await asyncio.to_thread(_run_startup_ingest)

    ingest_task = None
    if INGEST_BACKGROUND:
        ingest_task = asyncio.create_task(_ingest_loop())

    yield

    if ingest_task is not None:
        ingest_task.cancel()
        try:
            await ingest_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="TechPulse API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _news_to_response(item: NewsItem) -> NewsItemResponse:
    return NewsItemResponse(
        id=item.id,
        title=item.title,
        title_original=item.title_original,
        description=item.description,
        url=item.url,
        source=item.source,
        ai_relevance=item.ai_relevance,
        hype_score=item.hype_score,
        ai_reasoning=item.ai_reasoning,
        is_read=item.is_read,
        is_bookmarked=item.is_bookmarked,
        folder_id=item.folder_id,
        folder_name=item.folder.name if item.folder else None,
        created_at=item.created_at,
    )


def _apply_news_filters(
    query,
    *,
    is_read: bool | None,
    is_bookmarked: bool | None,
    ai_relevance: str | None,
    folder_id: int | None,
    source: str | None,
    min_hype: int | None,
    hype: int | None,
    q: str | None,
):
    if is_read is not None:
        query = query.where(NewsItem.is_read == is_read)
    if is_bookmarked is not None:
        query = query.where(NewsItem.is_bookmarked == is_bookmarked)
    if ai_relevance is not None:
        query = query.where(NewsItem.ai_relevance == ai_relevance)
    if folder_id is not None:
        query = query.where(NewsItem.folder_id == folder_id)
    if source is not None:
        if source == "rss":
            query = query.where(NewsItem.source.startswith("rss/"))
        else:
            query = query.where(NewsItem.source == source)
    if min_hype is not None:
        query = query.where(NewsItem.hype_score >= min_hype)
    if hype is not None:
        query = query.where(NewsItem.hype_score == hype)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                NewsItem.title.ilike(pattern),
                NewsItem.title_original.ilike(pattern),
                NewsItem.description.ilike(pattern),
            )
        )
    return query


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", service="techpulse-api")


@app.get("/api/pipeline/steps", response_model=PipelineConfigResponse)
def get_pipeline_steps():
    return PipelineConfigResponse(
        ingest=[
            PipelineStepResponse(**step)
            for step in steps_to_dict(INGEST_PIPELINE_STEPS)
        ],
        backfill=[
            PipelineStepResponse(**step)
            for step in steps_to_dict(BACKFILL_PIPELINE_STEPS)
        ],
    )


@app.get("/api/news/count", response_model=NewsCountResponse)
def count_news(
    is_read: bool | None = Query(default=None),
    is_bookmarked: bool | None = Query(default=None),
    ai_relevance: str | None = Query(default=None),
    folder_id: int | None = Query(default=None),
    source: str | None = Query(default=None),
    min_hype: int | None = Query(default=None, ge=0, le=5),
    hype: int | None = Query(default=None, ge=0, le=5),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
):
    query = select(func.count()).select_from(NewsItem)
    query = _apply_news_filters(
        query,
        is_read=is_read,
        is_bookmarked=is_bookmarked,
        ai_relevance=ai_relevance,
        folder_id=folder_id,
        source=source,
        min_hype=min_hype,
        hype=hype,
        q=q,
    )
    total = db.scalar(query) or 0
    return NewsCountResponse(count=total)


@app.get("/api/news", response_model=NewsListResponse)
def list_news(
    is_read: bool | None = Query(default=None),
    is_bookmarked: bool | None = Query(default=None),
    ai_relevance: str | None = Query(default=None),
    folder_id: int | None = Query(default=None),
    source: str | None = Query(default=None),
    min_hype: int | None = Query(default=None, ge=0, le=5),
    hype: int | None = Query(default=None, ge=0, le=5),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    base = select(NewsItem).options(joinedload(NewsItem.folder))
    base = _apply_news_filters(
        base,
        is_read=is_read,
        is_bookmarked=is_bookmarked,
        ai_relevance=ai_relevance,
        folder_id=folder_id,
        source=source,
        min_hype=min_hype,
        hype=hype,
        q=q,
    )

    count_query = select(func.count()).select_from(NewsItem)
    count_query = _apply_news_filters(
        count_query,
        is_read=is_read,
        is_bookmarked=is_bookmarked,
        ai_relevance=ai_relevance,
        folder_id=folder_id,
        source=source,
        min_hype=min_hype,
        hype=hype,
        q=q,
    )
    total = db.scalar(count_query) or 0
    items = db.scalars(
        base.order_by(NewsItem.created_at.desc()).limit(limit).offset(offset)
    ).all()

    return NewsListResponse(
        items=[_news_to_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/api/folders", response_model=list[TopicFolderResponse])
def list_folders(db: Session = Depends(get_db)):
    folders = db.scalars(select(TopicFolder).order_by(TopicFolder.name)).all()
    counts = dict(
        db.execute(
            select(NewsItem.folder_id, func.count())
            .where(NewsItem.folder_id.is_not(None))
            .group_by(NewsItem.folder_id)
        ).all()
    )

    return [
        TopicFolderResponse(
            id=folder.id,
            name=folder.name,
            item_count=counts.get(folder.id, 0),
            created_at=folder.created_at,
        )
        for folder in folders
    ]


@app.post("/api/folders", response_model=TopicFolderResponse, status_code=201)
def create_folder(payload: TopicFolderCreate, db: Session = Depends(get_db)):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Nome da pasta é obrigatório")

    folder = TopicFolder(name=name)
    db.add(folder)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Já existe uma pasta com esse nome")
    db.refresh(folder)
    return TopicFolderResponse(
        id=folder.id,
        name=folder.name,
        item_count=0,
        created_at=folder.created_at,
    )


@app.delete("/api/folders/{folder_id}", response_model=BulkNewsResult)
def delete_folder(folder_id: int, db: Session = Depends(get_db)):
    folder = db.get(TopicFolder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Pasta não encontrada")

    items = db.scalars(select(NewsItem).where(NewsItem.folder_id == folder_id)).all()
    for item in items:
        item.folder_id = None

    db.delete(folder)
    db.commit()
    return BulkNewsResult(affected=len(items))


@app.post("/api/news", response_model=NewsItemResponse, status_code=201)
def create_news(item: NewsItemCreate, db: Session = Depends(get_db)):
    payload = item.model_dump()
    if not payload.get("title_original"):
        payload["title_original"] = payload["title"]
    db_item = NewsItem(**payload)
    db.add(db_item)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="URL já cadastrada")
    db.refresh(db_item)
    return db_item


@app.patch("/api/news/{item_id}/read", response_model=NewsItemResponse)
def update_read_status(
    item_id: int,
    payload: NewsItemReadUpdate,
    db: Session = Depends(get_db),
):
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    db_item.is_read = payload.is_read
    db.commit()
    db_item = db.scalar(
        select(NewsItem)
        .options(joinedload(NewsItem.folder))
        .where(NewsItem.id == item_id)
    )
    return _news_to_response(db_item)


@app.patch("/api/news/{item_id}/bookmark", response_model=NewsItemResponse)
def update_bookmark_status(
    item_id: int,
    payload: NewsItemBookmarkUpdate,
    db: Session = Depends(get_db),
):
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    db_item.is_bookmarked = payload.is_bookmarked
    if not payload.is_bookmarked:
        db_item.folder_id = None
    db.commit()
    db_item = db.scalar(
        select(NewsItem)
        .options(joinedload(NewsItem.folder))
        .where(NewsItem.id == item_id)
    )
    return _news_to_response(db_item)


@app.patch("/api/news/{item_id}/folder", response_model=NewsItemResponse)
def update_folder(
    item_id: int,
    payload: NewsItemFolderUpdate,
    db: Session = Depends(get_db),
):
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    if payload.folder_id is not None:
        folder = db.get(TopicFolder, payload.folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail="Pasta não encontrada")

    db_item.folder_id = payload.folder_id
    if payload.folder_id is not None:
        db_item.is_bookmarked = True

    db.commit()
    db_item = db.scalar(
        select(NewsItem)
        .options(joinedload(NewsItem.folder))
        .where(NewsItem.id == item_id)
    )
    return _news_to_response(db_item)


@app.patch("/api/news/bulk", response_model=BulkNewsResult)
def bulk_update_news(payload: BulkNewsUpdate, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")
    if (
        payload.is_read is None
        and payload.is_bookmarked is None
        and payload.folder_id is None
        and not payload.clear_folder
    ):
        raise HTTPException(status_code=400, detail="Nenhuma ação informada")

    if payload.folder_id is not None:
        folder = db.get(TopicFolder, payload.folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail="Pasta não encontrada")

    items = db.scalars(select(NewsItem).where(NewsItem.id.in_(payload.ids))).all()
    if not items:
        raise HTTPException(status_code=404, detail="Nenhuma notícia encontrada")

    for item in items:
        if payload.is_read is not None:
            item.is_read = payload.is_read
        if payload.is_bookmarked is not None:
            item.is_bookmarked = payload.is_bookmarked
        if payload.clear_folder:
            item.folder_id = None
        elif payload.folder_id is not None:
            item.folder_id = payload.folder_id
            item.is_bookmarked = True

    db.commit()
    return BulkNewsResult(affected=len(items))


@app.delete("/api/news/bulk", response_model=BulkNewsResult)
def bulk_delete_news(payload: BulkNewsDelete, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")

    items = db.scalars(select(NewsItem).where(NewsItem.id.in_(payload.ids))).all()
    if not items:
        raise HTTPException(status_code=404, detail="Nenhuma notícia encontrada")

    for item in items:
        db.delete(item)

    db.commit()
    return BulkNewsResult(affected=len(items))


@app.delete("/api/news/{item_id}", response_model=BulkNewsResult)
def delete_news(item_id: int, db: Session = Depends(get_db)):
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    db.delete(db_item)
    db.commit()
    return BulkNewsResult(affected=1)


@app.get("/api/obsidian/status", response_model=ObsidianStatusResponse)
def obsidian_status():
    config = get_obsidian_config()
    connected: bool | None = None
    message: str | None = None

    if config["mode"] == "rest":
        connected, message = check_rest_connection()
    elif config["mode"] == "filesystem":
        connected = True
        message = "Gravação direta no vault configurada."

    if not config["configured"]:
        message = (
            "Configure OBSIDIAN_REST_API_KEY (plugin Local REST API) ou "
            "OBSIDIAN_VAULT_PATH no .env do backend."
        )

    return ObsidianStatusResponse(
        configured=config["configured"],
        mode=config["mode"],
        folder=config["folder"],
        connected=connected,
        message=message,
    )


@app.post("/api/obsidian/export", response_model=ObsidianExportResult)
def export_to_obsidian(payload: ObsidianExportRequest, db: Session = Depends(get_db)):
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")

    items = db.scalars(
        select(NewsItem).where(NewsItem.id.in_(payload.ids)).order_by(NewsItem.created_at.desc())
    ).all()
    if not items:
        raise HTTPException(status_code=404, detail="Nenhuma notícia encontrada")

    try:
        result = export_items_to_obsidian(items)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if result["exported"] == 0:
        raise HTTPException(
            status_code=500,
            detail="Nenhuma nota exportada. " + "; ".join(result["errors"]),
        )

    return ObsidianExportResult(**result)


@app.post("/api/ingest", response_model=IngestResult)
async def trigger_ingest(db: Session = Depends(get_db)):
    return await asyncio.to_thread(run_ingest, db)


@app.post("/api/ingest/stream")
async def trigger_ingest_stream(request: Request, db: Session = Depends(get_db)):
    def job(emit):
        return run_ingest(db, on_progress=emit)

    return _stream_sync_job(job, request)


@app.post("/api/seed", response_model=SeedResult)
async def seed_demo(db: Session = Depends(get_db)):
    if os.getenv("ALLOW_SEED", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Endpoint de seed desabilitado")
    return await asyncio.to_thread(seed_demo_articles, db)


@app.post("/api/enrich-backfill", response_model=EnrichBackfillResult)
async def enrich_backfill(
    limit: int = Query(default=1, ge=1, le=5),
    db: Session = Depends(get_db),
):
    return await asyncio.to_thread(enrich_missing_items, db, limit)


@app.post("/api/enrich-backfill/stream")
async def enrich_backfill_stream(
    request: Request,
    limit: int = Query(default=1, ge=1, le=5),
    db: Session = Depends(get_db),
):
    def job(emit):
        return enrich_missing_items(db, limit, on_progress=emit)

    return _stream_sync_job(job, request)
