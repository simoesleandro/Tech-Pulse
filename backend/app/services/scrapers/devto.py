import requests

from app.services.scrapers.base import RawArticle

DEVTO_API_URL = "https://dev.to/api/articles"
DEFAULT_LIMIT = 10
REQUEST_TIMEOUT = 15


def fetch_devto(limit: int = DEFAULT_LIMIT) -> list[RawArticle]:
    response = requests.get(
        DEVTO_API_URL,
        params={"per_page": limit},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    articles: list[RawArticle] = []
    for item in response.json():
        title = item.get("title", "").strip()
        url = item.get("url", "").strip()
        if title and url:
            articles.append(RawArticle(title=title, url=url, source="dev.to"))
    return articles
