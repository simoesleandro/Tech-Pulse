import logging

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
DEFAULT_LIMIT = 15


def fetch_hacker_news(limit: int = DEFAULT_LIMIT) -> list[RawArticle]:
    response = requests.get(HN_TOP_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    story_ids = response.json()[:limit]
    articles: list[RawArticle] = []

    for item_id in story_ids:
        try:
            item_response = requests.get(
                HN_ITEM_URL.format(item_id=item_id),
                timeout=REQUEST_TIMEOUT,
            )
            item_response.raise_for_status()
            item = item_response.json()
        except requests.RequestException as exc:
            logger.warning("HN item %s failed: %s", item_id, exc)
            continue

        title = (item.get("title") or "").strip()
        if not title:
            continue

        url = (item.get("url") or "").strip()
        if not url:
            url = f"https://news.ycombinator.com/item?id={item_id}"

        articles.append(
            RawArticle(
                title=title,
                url=url,
                source="hacker_news",
                description_snippet=f"Discussão no Hacker News (ID {item_id}).",
                ups=int(item.get("score", 0) or 0),
                comments_count=int(item.get("descendants", 0) or 0),
            )
        )

    return articles
