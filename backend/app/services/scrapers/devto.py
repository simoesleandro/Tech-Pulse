import logging

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

DEVTO_API_URL = "https://dev.to/api/articles"
DEFAULT_TAGS = (
    "javascript",
    "react",
    "node",
    "typescript",
    "css",
    "webdev",
    "ai",
    "llm",
    "python",
    "nextjs",
)
DEFAULT_LIMIT = 8


def fetch_devto_by_tag(tag: str, limit: int = DEFAULT_LIMIT) -> list[RawArticle]:
    response = requests.get(
        DEVTO_API_URL,
        params={"tag": tag, "per_page": limit},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    articles: list[RawArticle] = []
    for item in response.json():
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        if title and url:
            articles.append(
                RawArticle(
                    title=title,
                    url=url,
                    source="dev.to",
                    description_snippet=item.get("description", "").strip(),
                    positive_reactions=int(item.get("positive_reactions_count", 0) or 0),
                    comments_count=int(item.get("comments_count", 0) or 0),
                )
            )
    return articles


def fetch_devto(
    tags: tuple[str, ...] = DEFAULT_TAGS,
    limit: int = DEFAULT_LIMIT,
) -> list[RawArticle]:
    articles: list[RawArticle] = []
    seen_urls: set[str] = set()

    for tag in tags:
        try:
            batch = fetch_devto_by_tag(tag, limit=limit)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("dev.to fetch failed for tag %s: %s", tag, exc)
            continue

        for article in batch:
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            articles.append(article)

    return articles
