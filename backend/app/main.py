from contextlib import asynccontextmanager
import asyncio
import logging
import os

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine, get_db
from app.models import NewsItem
from app.schemas import (
    IngestResult,
    NewsItemBookmarkUpdate,
    NewsItemCreate,
    NewsItemReadUpdate,
    NewsItemResponse,
)
from app.services.ingest import run_ingest

logger = logging.getLogger(__name__)

INGEST_INTERVAL_SECONDS = int(os.getenv("INGEST_INTERVAL_SECONDS", "300"))
INGEST_ON_STARTUP = os.getenv("INGEST_ON_STARTUP", "false").lower() == "true"
INGEST_BACKGROUND = os.getenv("INGEST_BACKGROUND", "false").lower() == "true"


async def _ingest_loop() -> None:
    while True:
        await asyncio.sleep(INGEST_INTERVAL_SECONDS)
        db = SessionLocal()
        try:
            stats = run_ingest(db)
            logger.info("Ingestão em background concluída: %s", stats)
        except Exception:
            logger.exception("Falha na ingestão em background")
        finally:
            db.close()


def _run_startup_ingest() -> None:
    db = SessionLocal()
    try:
        stats = run_ingest(db)
        logger.info("Ingestão inicial concluída: %s", stats)
    except Exception:
        logger.exception("Falha na ingestão inicial")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

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


@app.get("/api/news", response_model=list[NewsItemResponse])
def list_news(
    is_read: bool | None = Query(default=None),
    ai_relevance: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    query = select(NewsItem)

    if is_read is not None:
        query = query.where(NewsItem.is_read == is_read)
    if ai_relevance is not None:
        query = query.where(NewsItem.ai_relevance == ai_relevance)

    query = query.order_by(NewsItem.created_at.desc())
    return db.scalars(query).all()


@app.post("/api/news", response_model=NewsItemResponse, status_code=201)
def create_news(item: NewsItemCreate, db: Session = Depends(get_db)):
    db_item = NewsItem(**item.model_dump())
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
    db.refresh(db_item)
    return db_item


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
    db.commit()
    db.refresh(db_item)
    return db_item


@app.post("/api/ingest", response_model=IngestResult)
def trigger_ingest(db: Session = Depends(get_db)):
    return run_ingest(db)
