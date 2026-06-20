"""Agregações para o painel de analytics pessoal."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session

from app.models import NewsItem, TopicFolder
from app.schemas import AnalyticsResponse, FolderStats, IngestByDay, SourceStats

logger = logging.getLogger(__name__)


def get_analytics(db: Session, *, days: int = 30) -> AnalyticsResponse:
    """Calcula métricas de uso dos últimos `days` dias."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Totais gerais
    base_filter = NewsItem.created_at >= cutoff
    total_items = db.scalar(
        select(func.count()).select_from(NewsItem).where(base_filter)
    ) or 0
    relevant_items = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.ai_relevance == "RELEVANTE")
    ) or 0
    read_items = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.is_read.is_(True))
    ) or 0
    bookmarked_items = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.is_bookmarked.is_(True))
    ) or 0
    feedback_given = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.user_relevance.isnot(None))
    ) or 0

    # Stats por fonte
    source_rows = db.execute(
        select(
            NewsItem.source,
            func.count().label("total"),
            func.sum(
                case((NewsItem.ai_relevance == "RELEVANTE", 1), else_=0)
            ).label("relevante"),
            func.avg(NewsItem.hype_score).label("avg_hype"),
        )
        .where(base_filter)
        .group_by(NewsItem.source)
        .order_by(func.count().desc())
        .limit(20)
    ).fetchall()

    sources: list[SourceStats] = []
    for row in source_rows:
        total = row.total or 0
        relevante = row.relevante or 0
        sources.append(SourceStats(
            source=row.source,
            total=total,
            relevante=relevante,
            relevance_rate=round(relevante / total, 3) if total > 0 else 0.0,
            avg_hype=round(float(row.avg_hype or 0), 2),
        ))

    # Ingest por dia — SQLite: strftime para truncar ao dia
    day_rows = db.execute(
        text(
            """
            SELECT
                strftime('%Y-%m-%d', created_at) AS day,
                COUNT(*) AS total,
                SUM(CASE WHEN ai_relevance = 'RELEVANTE' THEN 1 ELSE 0 END) AS relevante
            FROM news_items
            WHERE created_at >= :cutoff
            GROUP BY day
            ORDER BY day DESC
            LIMIT :days
            """
        ),
        {"cutoff": cutoff.isoformat(), "days": days},
    ).fetchall()

    ingest_by_day: list[IngestByDay] = [
        IngestByDay(date=row.day, total=row.total or 0, relevante=row.relevante or 0)
        for row in day_rows
    ]

    # Top pastas por número de itens
    folder_rows = db.execute(
        select(
            NewsItem.folder_id,
            TopicFolder.name.label("folder_name"),
            func.count().label("item_count"),
        )
        .outerjoin(TopicFolder, NewsItem.folder_id == TopicFolder.id)
        .where(base_filter)
        .where(NewsItem.is_bookmarked.is_(True))
        .group_by(NewsItem.folder_id, TopicFolder.name)
        .order_by(func.count().desc())
        .limit(10)
    ).fetchall()

    top_folders: list[FolderStats] = [
        FolderStats(
            folder_id=row.folder_id,
            folder_name=row.folder_name,
            item_count=row.item_count or 0,
        )
        for row in folder_rows
    ]

    return AnalyticsResponse(
        period_days=days,
        total_items=total_items,
        relevant_items=relevant_items,
        read_items=read_items,
        bookmarked_items=bookmarked_items,
        feedback_given=feedback_given,
        sources=sources,
        ingest_by_day=ingest_by_day,
        top_folders=top_folders,
    )
