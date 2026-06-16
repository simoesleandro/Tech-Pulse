import requests

from app.services.scrapers.base import RawArticle

REDDIT_API_URL = "https://www.reddit.com/r/{subreddit}/hot.json"
DEFAULT_SUBREDDIT = "programming"
DEFAULT_LIMIT = 10
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; TechPulseBot/1.0; +https://github.com/simoesleandro/Tech-Pulse)"


def fetch_reddit(
    subreddit: str = DEFAULT_SUBREDDIT, limit: int = DEFAULT_LIMIT
) -> list[RawArticle]:
    response = requests.get(
        REDDIT_API_URL.format(subreddit=subreddit),
        params={"limit": limit},
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    articles: list[RawArticle] = []
    for child in response.json().get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied"):
            continue

        title = post.get("title", "").strip()
        url = post.get("url", "").strip()
        if title and url:
            articles.append(
                RawArticle(
                    title=title,
                    url=url,
                    source="reddit",
                    description_snippet=post.get("selftext", "").strip()[:280],
                    ups=int(post.get("ups", 0) or 0),
                )
            )
    return articles
