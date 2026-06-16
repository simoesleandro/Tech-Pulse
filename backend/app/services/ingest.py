import functools
import logging
from collections.abc import Callable

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services.hype_backfill import (
    apply_engagement_from_article,
    item_to_raw_article,
    refresh_item_hype,
    resolve_hype_score,
)
from app.services.ollama import enrich_article
from app.services.scrapers import (
    fetch_devto,
    fetch_github_trends,
    fetch_hacker_news,
    fetch_reddit,
    fetch_rss_feeds,
)
from app.services.scrapers.base import RawArticle

logger = logging.getLogger(__name__)

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


def _persist_article(db: Session, article: RawArticle, enriched) -> NewsItem:
    hype_score = resolve_hype_score(enriched.hype_score, article)
    db_item = NewsItem(
        title=enriched.title_pt,
        title_original=article.title,
        description=enriched.description_pt,
        url=article.url,
        source=article.source,
        ai_relevance=enriched.ai_relevance,
        hype_score=hype_score,
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


def run_ingest(
    db: Session,
    fetchers: list[Fetcher] | None = None,
    enricher: Callable[[RawArticle], object] = enrich_article,
) -> dict:
    fetchers = fetchers or DEFAULT_FETCHERS
    existing_urls = _load_existing_urls(db)
    articles, scraper_errors = _fetch_all_articles(fetchers)

    stats = {
        "fetched": len(articles),
        "skipped_duplicate": 0,
        "classified": 0,
        "saved": 0,
        "relevante": 0,
        "lixo": 0,
        "errors": list(scraper_errors),
    }

    for article in articles:
        if article.url in existing_urls:
            stats["skipped_duplicate"] += 1
            continue

        try:
            enriched = enricher(article)
            stats["classified"] += 1

            _persist_article(db, article, enriched)
            existing_urls.add(article.url)
            stats["saved"] += 1
            if enriched.ai_relevance == "RELEVANTE":
                stats["relevante"] += 1
            else:
                stats["lixo"] += 1
        except IntegrityError:
            db.rollback()
            existing_urls.add(article.url)
            stats["skipped_duplicate"] += 1
        except Exception as exc:
            db.rollback()
            stats["errors"].append(f"{article.url}: {exc}")

    return stats


def enrich_missing_items(db: Session, limit: int = 1) -> dict[str, int]:
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

    for item in items:
        try:
            if item.is_enriched and item.hype_score == 0:
                refresh_item_hype(item)
                db.commit()
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

            enriched = enrich_article(raw)
            item.title = enriched.title_pt
            item.title_original = raw.title
            item.description = enriched.description_pt
            item.ai_relevance = enriched.ai_relevance
            apply_engagement_from_article(item, raw)
            item.hype_score = resolve_hype_score(enriched.hype_score, raw)
            if item.hype_score == 0:
                refresh_item_hype(item)
            item.is_enriched = True
            db.commit()
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
