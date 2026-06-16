import asyncio
import functools
import logging
import threading
from collections.abc import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services.ai_agent import (
    AgentProgressCallback,
    enrich_article_sync,
    enrich_articles_as_completed,
)
from app.services.hype_backfill import (
    apply_engagement_from_article,
    item_to_raw_article,
    refresh_item_hype,
    resolve_hype_score,
)
from app.services.pipeline_progress import ProgressEmitter, emit_step
from app.services.scrapers import (
    fetch_devto,
    fetch_github_trends,
    fetch_hacker_news,
    fetch_reddit,
    fetch_rss_feeds,
)
from app.services.scrapers.base import EnrichedArticle, RawArticle

logger = logging.getLogger(__name__)

CancelCheck = Callable[[], bool]

_ingest_cancel_flag = threading.local()


def set_ingest_cancel_event(event: threading.Event | None) -> None:
    _ingest_cancel_flag.event = event


def _is_cancelled() -> bool:
    event = getattr(_ingest_cancel_flag, "event", None)
    return bool(event and event.is_set())


def _raise_if_cancelled() -> None:
    if _is_cancelled():
        raise InterruptedError("Ingestão cancelada — conexão encerrada.")


Fetcher = Callable[[], list[RawArticle]]


def _fetcher_name(fetcher: Fetcher) -> str:
    if isinstance(fetcher, functools.partial):
        return getattr(fetcher.func, "__name__", "partial_fetcher")
    return getattr(fetcher, "__name__", "fetcher")


DEFAULT_FETCHERS: list[Fetcher] = [
    fetch_devto,
    fetch_reddit,
    fetch_github_trends,
    fetch_hacker_news,
    fetch_rss_feeds,
]


def _load_existing_urls(db: Session) -> set[str]:
    return set(db.scalars(select(NewsItem.url)).all())


def _fetch_all_articles(fetchers: list[Fetcher]) -> tuple[list[RawArticle], list[str]]:
    articles: list[RawArticle] = []
    errors: list[str] = []

    for fetcher in fetchers:
        name = _fetcher_name(fetcher)
        try:
            articles.extend(fetcher())
        except Exception as exc:
            message = f"{name}: {exc}"
            logger.warning("Scraper failed %s", message)
            errors.append(message)

    return articles, errors


def _count_pending(db: Session) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(NewsItem)
            .where(
                or_(
                    NewsItem.is_enriched.is_(False),
                    NewsItem.hype_score == 0,
                )
            )
        )
        or 0
    )


def _persist_article(db: Session, article: RawArticle, enriched: EnrichedArticle) -> NewsItem:
    hype_score = resolve_hype_score(enriched.hype_score, article)
    db_item = NewsItem(
        title=enriched.title_pt,
        title_original=article.title,
        description=enriched.description_pt,
        url=article.url,
        source=article.source,
        ai_relevance=enriched.ai_relevance,
        hype_score=hype_score,
        ai_reasoning=enriched.ai_reasoning,
        engagement_reactions=article.positive_reactions,
        engagement_comments=article.comments_count,
        engagement_stars=article.stars,
        engagement_ups=article.ups,
        is_enriched=True,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def _agent_progress_factory(
    on_progress: ProgressEmitter | None,
    article_index: int,
    article_total: int,
) -> AgentProgressCallback:
    def on_agent_progress(step_id: str, status: str, detail: str | None = None) -> None:
        label = detail or f"artigo {article_index}/{article_total}"
        emit_step(
            on_progress,
            step_id,
            status,
            label,
            article_index=article_index,
            article_total=article_total,
        )

    return on_agent_progress


def _persist_enriched_result(
    db: Session,
    index: int,
    article: RawArticle,
    enriched: EnrichedArticle,
    on_progress: ProgressEmitter | None,
    total_pending: int,
    existing_urls: set[str],
    stats: dict,
) -> None:
    stats["classified"] += 1

    emit_step(
        on_progress,
        "save",
        "active",
        f"salvando artigo {index}/{total_pending} no SQLite…",
        article_index=index,
        article_total=total_pending,
    )
    _persist_article(db, article, enriched)
    emit_step(
        on_progress,
        "save",
        "done",
        f"artigo {index}/{total_pending} salvo · {enriched.title_pt[:60]}",
        article_index=index,
        article_total=total_pending,
    )

    existing_urls.add(article.url)
    stats["saved"] += 1
    if enriched.ai_relevance == "RELEVANTE":
        stats["relevante"] += 1
    else:
        stats["lixo"] += 1


async def _enrich_and_persist_streaming(
    db: Session,
    pending: list[RawArticle],
    on_progress: ProgressEmitter | None,
    total_pending: int,
    existing_urls: set[str],
    stats: dict,
) -> None:
    def factory(index: int, total: int) -> AgentProgressCallback:
        return _agent_progress_factory(on_progress, index, total)

    async for index, article, outcome in enrich_articles_as_completed(pending, factory):
        _raise_if_cancelled()

        if isinstance(outcome, Exception):
            stats["errors"].append(f"{article.url}: {outcome}")
            continue

        try:
            _persist_enriched_result(
                db,
                index,
                article,
                outcome,
                on_progress,
                total_pending,
                existing_urls,
                stats,
            )
        except IntegrityError:
            db.rollback()
            existing_urls.add(article.url)
            stats["skipped_duplicate"] += 1
        except Exception as exc:
            db.rollback()
            stats["errors"].append(f"{article.url}: {exc}")


def _run_streaming_enrich(
    db: Session,
    pending: list[RawArticle],
    on_progress: ProgressEmitter | None,
    total_pending: int,
    existing_urls: set[str],
    stats: dict,
) -> None:
    asyncio.run(
        _enrich_and_persist_streaming(
            db,
            pending,
            on_progress,
            total_pending,
            existing_urls,
            stats,
        )
    )


def _enrich_with_progress(
    article: RawArticle,
    on_progress: ProgressEmitter | None,
    article_index: int,
    article_total: int,
) -> EnrichedArticle:
    return enrich_article_sync(
        article,
        on_agent_progress=_agent_progress_factory(on_progress, article_index, article_total),
    )


def run_ingest(
    db: Session,
    fetchers: list[Fetcher] | None = None,
    enricher: Callable[[RawArticle], object] | None = None,
    on_progress: ProgressEmitter | None = None,
) -> dict:
    fetchers = fetchers or DEFAULT_FETCHERS
    existing_urls = _load_existing_urls(db)

    emit_step(on_progress, "fetch", "active")
    articles, scraper_errors = _fetch_all_articles(fetchers)
    emit_step(on_progress, "fetch", "done", f"{len(articles)} artigos capturados")

    emit_step(on_progress, "dedup", "active")
    pending = [article for article in articles if article.url not in existing_urls]
    emit_step(
        on_progress,
        "dedup",
        "done",
        f"{len(articles) - len(pending)} duplicadas ignoradas · {len(pending)} novos",
    )

    stats = {
        "fetched": len(articles),
        "skipped_duplicate": len(articles) - len(pending),
        "classified": 0,
        "saved": 0,
        "relevante": 0,
        "lixo": 0,
        "errors": list(scraper_errors),
    }

    total_pending = len(pending)

    _raise_if_cancelled()

    if enricher is not None:
        for index, article in enumerate(pending, start=1):
            _raise_if_cancelled()
            try:
                enriched = enricher(article)
                _persist_enriched_result(
                    db,
                    index,
                    article,
                    enriched,
                    on_progress,
                    total_pending,
                    existing_urls,
                    stats,
                )
            except IntegrityError:
                db.rollback()
                existing_urls.add(article.url)
                stats["skipped_duplicate"] += 1
            except Exception as exc:
                db.rollback()
                stats["errors"].append(f"{article.url}: {exc}")
    else:
        _run_streaming_enrich(
            db,
            pending,
            on_progress,
            total_pending,
            existing_urls,
            stats,
        )

    return stats


def enrich_missing_items(
    db: Session,
    limit: int = 1,
    on_progress: ProgressEmitter | None = None,
) -> dict[str, int]:
    pending_before = _count_pending(db)
    items = db.scalars(
        select(NewsItem)
        .where(
            or_(
                NewsItem.is_enriched.is_(False),
                NewsItem.hype_score == 0,
            )
        )
        .order_by(NewsItem.created_at.desc())
        .limit(limit)
    ).all()

    processed = 0
    errors = 0
    error_messages: list[str] = []

    emit_step(on_progress, "pick", "active", f"{len(items)} selecionado(s)")

    for index, item in enumerate(items, start=1):
        try:
            if item.is_enriched and item.hype_score == 0:
                emit_step(on_progress, "hype", "active", "recalculando hype")
                refresh_item_hype(item)
                db.commit()
                emit_step(on_progress, "hype", "done", f"{item.hype_score} estrelas")
                processed += 1
                continue

            raw = item_to_raw_article(item)
            if not raw.description_snippet and item.description:
                raw = RawArticle(
                    title=raw.title,
                    url=raw.url,
                    source=raw.source,
                    description_snippet=item.description,
                    positive_reactions=item.engagement_reactions,
                    comments_count=item.engagement_comments,
                    stars=item.engagement_stars,
                    ups=item.engagement_ups,
                )

            emit_step(on_progress, "pick", "done", raw.title[:80])

            enriched = _enrich_with_progress(
                raw,
                on_progress,
                article_index=index,
                article_total=len(items),
            )

            emit_step(on_progress, "save", "active", raw.title[:80])
            item.title = enriched.title_pt
            item.title_original = raw.title
            item.description = enriched.description_pt
            item.ai_relevance = enriched.ai_relevance
            item.ai_reasoning = enriched.ai_reasoning
            apply_engagement_from_article(item, raw)
            item.hype_score = resolve_hype_score(enriched.hype_score, raw)
            if item.hype_score == 0:
                refresh_item_hype(item)
            item.is_enriched = True
            db.commit()
            emit_step(on_progress, "save", "done", enriched.title_pt[:80])
            processed += 1
        except Exception as exc:
            db.rollback()
            errors += 1
            error_messages.append(f"{item.url}: {exc}")
            logger.warning("Backfill failed for %s: %s", item.url, exc)

    remaining = _count_pending(db)

    return {
        "processed": processed,
        "errors": errors,
        "candidates": pending_before,
        "remaining": remaining,
        "error_messages": error_messages,
    }
