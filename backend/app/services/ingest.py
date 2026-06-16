import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services.ollama import classify_title
from app.services.scrapers import fetch_devto, fetch_github_trends, fetch_reddit
from app.services.scrapers.base import RawArticle

logger = logging.getLogger(__name__)

Fetcher = Callable[[], list[RawArticle]]

DEFAULT_FETCHERS: list[Fetcher] = [fetch_devto, fetch_reddit, fetch_github_trends]


def _load_existing_urls(db: Session) -> set[str]:
    return set(db.scalars(select(NewsItem.url)).all())


def _fetch_all_articles(fetchers: list[Fetcher]) -> tuple[list[RawArticle], list[str]]:
    articles: list[RawArticle] = []
    errors: list[str] = []

    for fetcher in fetchers:
        name = fetcher.__name__
        try:
            articles.extend(fetcher())
        except Exception as exc:
            message = f"{name}: {exc}"
            logger.warning("Falha no scraper %s", message)
            errors.append(message)

    return articles, errors


def run_ingest(
    db: Session,
    fetchers: list[Fetcher] | None = None,
    classifier: Callable[[str], str] = classify_title,
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
            relevance = classifier(article.title)
            stats["classified"] += 1

            db_item = NewsItem(
                title=article.title,
                url=article.url,
                source=article.source,
                ai_relevance=relevance,
            )
            db.add(db_item)
            db.commit()
            db.refresh(db_item)

            existing_urls.add(article.url)
            stats["saved"] += 1
            if relevance == "RELEVANTE":
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
