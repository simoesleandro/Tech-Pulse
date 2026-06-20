import asyncio
import os

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_api_key
from app.models import NewsItem, TopicFolder
from app.repositories.folders import get_folder, list_folders_with_counts
from app.repositories.news import (
    get_news_by_ids,
    get_news_with_folder,
    list_news_filtered,
    news_to_response,
    count_news_filtered,
)
from app.schemas import (
    BulkNewsDelete,
    BulkNewsResult,
    BulkNewsUpdate,
    NewsCountResponse,
    NewsItemBookmarkUpdate,
    NewsItemCreate,
    NewsItemFolderUpdate,
    NewsItemReadUpdate,
    NewsItemResponse,
    NewsListResponse,
    ObsidianConceptResponse,
    TopicFolderCreate,
    TopicFolderResponse,
)
from app.services.concepts import extract_feed_concepts
from sqlalchemy import select

router = APIRouter(tags=["news"])


@router.get("/api/news/concepts", response_model=list[ObsidianConceptResponse])
def get_news_concepts(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return extract_feed_concepts(db, limit=limit)


@router.get("/api/news/count", response_model=NewsCountResponse)
def count_news(
    is_read: bool | None = Query(default=None),
    is_bookmarked: bool | None = Query(default=None),
    ai_relevance: str | None = Query(default=None),
    folder_id: int | None = Query(default=None),
    source: str | None = Query(default=None),
    min_hype: int | None = Query(default=None, ge=0, le=5),
    hype: int | None = Query(default=None, ge=0, le=5),
    obsidian_exported: bool | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    db: Session = Depends(get_db),
):
    total = count_news_filtered(
        db,
        is_read=is_read,
        is_bookmarked=is_bookmarked,
        ai_relevance=ai_relevance,
        folder_id=folder_id,
        source=source,
        min_hype=min_hype,
        hype=hype,
        obsidian_exported=obsidian_exported,
        q=q,
    )
    return NewsCountResponse(count=total)


@router.get("/api/news", response_model=NewsListResponse)
def list_news(
    is_read: bool | None = Query(default=None),
    is_bookmarked: bool | None = Query(default=None),
    ai_relevance: str | None = Query(default=None),
    folder_id: int | None = Query(default=None),
    source: str | None = Query(default=None),
    min_hype: int | None = Query(default=None, ge=0, le=5),
    hype: int | None = Query(default=None, ge=0, le=5),
    obsidian_exported: bool | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    items, total = list_news_filtered(
        db,
        limit=limit,
        offset=offset,
        is_read=is_read,
        is_bookmarked=is_bookmarked,
        ai_relevance=ai_relevance,
        folder_id=folder_id,
        source=source,
        min_hype=min_hype,
        hype=hype,
        obsidian_exported=obsidian_exported,
        q=q,
    )
    return NewsListResponse(
        items=[news_to_response(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/api/folders", response_model=list[TopicFolderResponse])
def list_folders(db: Session = Depends(get_db)):
    return list_folders_with_counts(db)


@router.post("/api/folders", response_model=TopicFolderResponse, status_code=201, dependencies=[Depends(require_api_key)])
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


@router.delete("/api/folders/{folder_id}", response_model=BulkNewsResult, dependencies=[Depends(require_api_key)])
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


@router.post("/api/news", response_model=NewsItemResponse, status_code=201, dependencies=[Depends(require_api_key)])
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
    return news_to_response(db_item)


@router.patch("/api/news/{item_id}/read", response_model=NewsItemResponse, dependencies=[Depends(require_api_key)])
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
    db_item = get_news_with_folder(db, item_id)
    return news_to_response(db_item)


@router.patch("/api/news/{item_id}/bookmark", response_model=NewsItemResponse, dependencies=[Depends(require_api_key)])
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
    db_item = get_news_with_folder(db, item_id)
    return news_to_response(db_item)


@router.patch("/api/news/{item_id}/relevance", response_model=NewsItemResponse, dependencies=[Depends(require_api_key)])
def update_relevance_feedback(
    item_id: int,
    relevance: str = Query(pattern="^(RELEVANTE|LIXO)$"),
    db: Session = Depends(get_db),
):
    """User feedback — overrides ai_relevance and updates the few-shot cache."""
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    db_item.user_relevance = relevance
    db_item.ai_relevance = relevance
    db.commit()

    # Refresh the few-shot cache used by the triador/unified agents
    from app.services.ai_agent import update_feedback_cache
    examples = [
        {"title": i.title_original, "source": i.source, "verdict": i.user_relevance}
        for i in db.scalars(
            select(NewsItem)
            .where(NewsItem.user_relevance.isnot(None))
            .order_by(NewsItem.created_at.desc())
            .limit(20)
        ).all()
    ]
    update_feedback_cache(examples)

    db_item = get_news_with_folder(db, item_id)
    return news_to_response(db_item)


@router.patch("/api/news/{item_id}/folder", response_model=NewsItemResponse, dependencies=[Depends(require_api_key)])
def update_folder(
    item_id: int,
    payload: NewsItemFolderUpdate,
    db: Session = Depends(get_db),
):
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    if payload.folder_id is not None:
        folder = get_folder(db, payload.folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail="Pasta não encontrada")

    db_item.folder_id = payload.folder_id
    if payload.folder_id is not None:
        db_item.is_bookmarked = True

    db.commit()
    db_item = get_news_with_folder(db, item_id)
    return news_to_response(db_item)


@router.patch("/api/news/bulk", response_model=BulkNewsResult, dependencies=[Depends(require_api_key)])
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
        folder = get_folder(db, payload.folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail="Pasta não encontrada")

    items = get_news_by_ids(db, payload.ids)
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


@router.delete("/api/news/bulk", response_model=BulkNewsResult, dependencies=[Depends(require_api_key)])
def bulk_delete_news(payload: BulkNewsDelete, db: Session = Depends(get_db)):
    return _bulk_delete_news(payload, db)


@router.post("/api/news/bulk/delete", response_model=BulkNewsResult, dependencies=[Depends(require_api_key)])
def bulk_delete_news_post(payload: BulkNewsDelete, db: Session = Depends(get_db)):
    return _bulk_delete_news(payload, db)


def _bulk_delete_news(payload: BulkNewsDelete, db: Session) -> BulkNewsResult:
    if not payload.ids:
        raise HTTPException(status_code=400, detail="Nenhum item selecionado")

    items = get_news_by_ids(db, payload.ids)
    if not items:
        raise HTTPException(status_code=404, detail="Nenhuma notícia encontrada")

    for item in items:
        db.delete(item)

    db.commit()
    return BulkNewsResult(affected=len(items))


@router.delete("/api/news/{item_id}", response_model=BulkNewsResult, dependencies=[Depends(require_api_key)])
def delete_news(item_id: int, db: Session = Depends(get_db)):
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    db.delete(db_item)
    db.commit()
    return BulkNewsResult(affected=1)
