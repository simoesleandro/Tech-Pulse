import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
DEFAULT_LIMIT = 15
MAX_FETCH_WORKERS = 8


def _fetch_hn_item(item_id: int) -> RawArticle | None:
    try:
        item_response = requests.get(
            HN_ITEM_URL.format(item_id=item_id),
            timeout=REQUEST_TIMEOUT,
        )
        item_response.raise_for_status()
        item = item_response.json()
    except requests.RequestException as exc:
        logger.warning("HN item %s failed: %s", item_id, exc)
        return None

    title = (item.get("title") or "").strip()
    if not title:
        return None

    url = (item.get("url") or "").strip()
    if not url:
        url = f"https://news.ycombinator.com/item?id={item_id}"

    return RawArticle(
        title=title,
        url=url,
        source="hacker_news",
        description_snippet=f"Discussão no Hacker News (ID {item_id}).",
        ups=int(item.get("score", 0) or 0),
        comments_count=int(item.get("descendants", 0) or 0),
    )


def fetch_hacker_news(limit: int = DEFAULT_LIMIT) -> list[RawArticle]:
    response = requests.get(HN_TOP_URL, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    story_ids = response.json()[:limit]
    articles: list[RawArticle] = []

    workers = min(MAX_FETCH_WORKERS, max(len(story_ids), 1))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_fetch_hn_item, item_id) for item_id in story_ids]
        for future in as_completed(futures):
            article = future.result()
            if article is not None:
                articles.append(article)

    return articles
