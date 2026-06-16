import requests

from app.services.scrapers.base import RawArticle

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
DEFAULT_LIMIT = 10
REQUEST_TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; TechPulseBot/1.0; +https://github.com/simoesleandro/Tech-Pulse)"


def fetch_github_trends(limit: int = DEFAULT_LIMIT) -> list[RawArticle]:
    response = requests.get(
        GITHUB_SEARCH_URL,
        params={
            "q": "stars:>500",
            "sort": "updated",
            "order": "desc",
            "per_page": limit,
        },
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
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
                    description_snippet=item.get("description", "").strip(),
                    stars=int(item.get("stargazers_count", 0) or 0),
                )
            )
    return articles
