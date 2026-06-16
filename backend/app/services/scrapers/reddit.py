import logging

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import BROWSER_HEADERS, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

REDDIT_JSON_URL = "https://www.reddit.com/r/{subreddit}/top/.json"
DEFAULT_SUBREDDITS = ("Python", "programming", "devops", "artificial")
DEFAULT_LIMIT = 10


def _resolve_post_url(post: dict) -> str:
    permalink = f"https://www.reddit.com{post.get('permalink', '')}"
    external = (post.get("url") or "").strip()

    if post.get("is_self") or not external or "reddit.com" in external:
        return permalink
    return external


def fetch_reddit_subreddit(
    subreddit: str, limit: int = DEFAULT_LIMIT
) -> list[RawArticle]:
    response = requests.get(
        REDDIT_JSON_URL.format(subreddit=subreddit),
        params={"limit": limit, "t": "week"},
        headers=BROWSER_HEADERS,
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code != 200:
        logger.warning("Reddit %s returned status %s", subreddit, response.status_code)
        return []

    articles: list[RawArticle] = []
    for child in response.json().get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied"):
            continue

        title = (post.get("title") or "").strip()
        url = _resolve_post_url(post)
        if not title or not url:
            continue

        snippet = (post.get("selftext") or "")[:280].strip()
        articles.append(
            RawArticle(
                title=title,
                url=url,
                source="reddit",
                description_snippet=snippet,
                ups=int(post.get("ups", 0) or 0),
                comments_count=int(post.get("num_comments", 0) or 0),
            )
        )
    return articles


def fetch_reddit(
    subreddits: tuple[str, ...] = DEFAULT_SUBREDDITS,
    limit: int = DEFAULT_LIMIT,
) -> list[RawArticle]:
    articles: list[RawArticle] = []
    seen_urls: set[str] = set()

    for subreddit in subreddits:
        try:
            batch = fetch_reddit_subreddit(subreddit, limit=limit)
        except requests.RequestException as exc:
            logger.warning("Reddit fetch failed for r/%s: %s", subreddit, exc)
            continue

        for article in batch:
            if article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            articles.append(article)

    return articles
