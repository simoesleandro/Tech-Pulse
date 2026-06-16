import functools
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services.hype import compute_hype_score
from app.services.ollama import enrich_article
from app.services.scrapers import fetch_devto, fetch_github_trends, fetch_reddit
from app.services.scrapers.base import RawArticle

logger = logging.getLogger(__name__)

Fetcher = Callable[[], list[RawArticle]]


def _fetcher_name(fetcher: Fetcher) -> str:
    if isinstance(fetcher, functools.partial):
        return getattr(fetcher.func, "__name__", "partial_fetcher")
    return getattr(fetcher, "__name__", "fetcher")


DEFAULT_FETCHERS: list[Fetcher] = [fetch_devto, fetch_reddit, fetch_github_trends]


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


def _persist_article(db: Session, article: RawArticle, enriched) -> NewsItem:
    db_item = NewsItem(
        title=enriched.title_pt,
        title_original=article.title,
        description=enriched.description_pt,
        url=article.url,
        source=article.source,
        ai_relevance=enriched.ai_relevance,
        hype_score=compute_hype_score(article),
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


def enrich_missing_items(db: Session) -> dict[str, int]:
    items = db.scalars(select(NewsItem).where(NewsItem.description == "")).all()

    processed = 0
    errors = 0

    for item in items:
        try:
            raw = RawArticle(
                title=item.title_original or item.title,
                url=item.url,
                source=item.source,
                description_snippet=item.description,
            )
            enriched = enrich_article(raw)
            item.title = enriched.title_pt
            item.title_original = raw.title
            item.description = enriched.description_pt
            item.ai_relevance = enriched.ai_relevance
            if item.hype_score == 0:
                item.hype_score = compute_hype_score(raw)
            db.commit()
            processed += 1
        except Exception as exc:
            db.rollback()
            errors += 1
            logger.warning("Backfill failed for %s: %s", item.url, exc)

    return {"processed": processed, "errors": errors, "candidates": len(items)}
