from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session, joinedload

from app.models import NewsItem
from app.schemas import NewsItemResponse


def news_to_response(item: NewsItem) -> NewsItemResponse:
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
        user_relevance=item.user_relevance,
        folder_id=item.folder_id,
        folder_name=item.folder.name if item.folder else None,
        obsidian_exported_at=item.obsidian_exported_at,
        engagement_reactions=item.engagement_reactions,
        engagement_comments=item.engagement_comments,
        engagement_stars=item.engagement_stars,
        engagement_ups=item.engagement_ups,
        created_at=item.created_at,
    )


def apply_news_filters(
    query,
    db: Session,
    *,
    is_read: bool | None,
    is_bookmarked: bool | None,
    ai_relevance: str | None,
    folder_id: int | None,
    source: str | None,
    min_hype: int | None,
    hype: int | None,
    obsidian_exported: bool | None,
    q: str | None,
):
    if is_read is not None:
        query = query.where(NewsItem.is_read == is_read)
    if is_bookmarked is not None:
        query = query.where(NewsItem.is_bookmarked == is_bookmarked)
    if ai_relevance is not None:
        query = query.where(NewsItem.ai_relevance == ai_relevance)
    if folder_id is not None:
        if folder_id == -1:
            query = query.where(NewsItem.folder_id.is_(None))
        else:
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
    if obsidian_exported is True:
        query = query.where(NewsItem.obsidian_exported_at.isnot(None))
    elif obsidian_exported is False:
        query = query.where(NewsItem.obsidian_exported_at.is_(None))
    if q:
        # FTS5 match — retorna apenas IDs que satisfazem a busca
        fts_query = q.strip().replace('"', '""')  # escapa aspas duplas para FTS5
        fts_ids = [
            row[0]
            for row in db.execute(
                text(
                    "SELECT rowid FROM news_fts WHERE news_fts MATCH :q ORDER BY rank"
                ),
                {"q": fts_query},
            ).fetchall()
        ]
        if fts_ids:
            query = query.where(NewsItem.id.in_(fts_ids))
        else:
            # Nenhum resultado FTS — retornar zero resultados
            query = query.where(NewsItem.id.is_(None))
    return query


def count_news_filtered(db: Session, **filters) -> int:
    query = select(func.count()).select_from(NewsItem)
    query = apply_news_filters(query, db, **filters)
    return db.scalar(query) or 0


def list_news_filtered(
    db: Session,
    *,
    limit: int,
    offset: int,
    **filters,
) -> tuple[list[NewsItem], int]:
    base = select(NewsItem).options(joinedload(NewsItem.folder))
    base = apply_news_filters(base, db, **filters)

    count_query = select(func.count()).select_from(NewsItem)
    count_query = apply_news_filters(count_query, db, **filters)
    total = db.scalar(count_query) or 0

    items = db.scalars(
        base.order_by(NewsItem.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total


def get_news_by_ids(db: Session, ids: list[int]) -> list[NewsItem]:
    return list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.id.in_(ids))
            .order_by(NewsItem.created_at.desc())
        ).all()
    )


def get_news_with_folder(db: Session, item_id: int) -> NewsItem | None:
    return db.scalar(
        select(NewsItem)
        .options(joinedload(NewsItem.folder))
        .where(NewsItem.id == item_id)
    )
