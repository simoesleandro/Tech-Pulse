import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import REQUEST_TIMEOUT

DEVTO_API_URL = "https://dev.to/api/articles"
DEFAULT_TAGS = ("python", "ai")
DEFAULT_LIMIT = 10


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
        for article in fetch_devto_by_tag(tag, limit=limit):
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            articles.append(article)

    return articles
