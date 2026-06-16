from datetime import UTC, datetime, timedelta

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import REQUEST_TIMEOUT

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_USER_AGENT = "Mozilla/5.0 (compatible; TechPulseBot/1.0; +https://github.com/simoesleandro/Tech-Pulse)"
DEFAULT_LIMIT = 10


def fetch_github_trends(limit: int = DEFAULT_LIMIT) -> list[RawArticle]:
    week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
    query = f"stars:>100 pushed:>{week_ago}"

    response = requests.get(
        GITHUB_SEARCH_URL,
        params={
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": limit,
        },
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": GITHUB_USER_AGENT,
        },
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()

    articles: list[RawArticle] = []
    for item in response.json().get("items", []):
        title = item.get("full_name", "").strip()
        url = item.get("html_url", "").strip()
        if title and url:
            articles.append(
                RawArticle(
                    title=title,
                    url=url,
                    source="github_trends",
                    description_snippet=(item.get("description") or "").strip(),
                    stars=int(item.get("stargazers_count", 0) or 0),
                )
            )
    return articles
