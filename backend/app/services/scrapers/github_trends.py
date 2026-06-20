import logging
import os
from datetime import UTC, datetime, timedelta

import requests

from app.services.scrapers.base import RawArticle
from app.services.scrapers.http_utils import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
GITHUB_USER_AGENT = (
    "Mozilla/5.0 (compatible; TechPulseBot/1.0; +https://github.com/simoesleandro/Tech-Pulse)"
)
DEFAULT_LIMIT = 35
PER_QUERY_LIMIT = 5
# Queries focadas em LLM, coding agents, web stack e repos novos úteis.
SEARCH_QUERY_SPECS: tuple[tuple[str, str, str], ...] = (
    ("hot_repos", "stars:>80 pushed:>{week_ago}", "stars"),
    ("new_repos", "stars:>35 created:>{week_ago}", "stars"),
    (
        "llm_ai",
        "(topic:llm OR topic:large-language-models OR topic:generative-ai) "
        "stars:>25 pushed:>{week_ago}",
        "stars",
    ),
    (
        "mcp_agents",
        "(topic:mcp OR topic:agents OR topic:agent) stars:>15 pushed:>{month_ago}",
        "stars",
    ),
    (
        "ai_coding_tools",
        "(cursor OR claude-code OR opencode OR \"coding agent\") "
        "in:name,description,readme stars:>10 pushed:>{month_ago}",
        "stars",
    ),
    (
        "react_next",
        "(topic:react OR topic:nextjs OR topic:next-js) stars:>40 pushed:>{week_ago}",
        "stars",
    ),
    (
        "nodejs_ts",
        "(topic:nodejs OR language:typescript) stars:>50 pushed:>{week_ago}",
        "stars",
    ),
    (
        "web_css",
        "(topic:css OR topic:tailwindcss OR topic:frontend) stars:>30 pushed:>{week_ago}",
        "stars",
    ),
)


def _github_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": GITHUB_USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _search_repositories(query: str, sort: str, per_page: int) -> list[dict]:
    response = requests.get(
        GITHUB_SEARCH_URL,
        params={
            "q": query,
            "sort": sort,
            "order": "desc",
            "per_page": per_page,
        },
        headers=_github_headers(),
        timeout=REQUEST_TIMEOUT,
    )

    if response.status_code == 403:
        logger.warning("GitHub API rate limit or forbidden: %s", response.text[:200])
        return []

    response.raise_for_status()
    return response.json().get("items", [])


def _repo_to_article(item: dict) -> RawArticle | None:
    title = item.get("full_name", "").strip()
    url = item.get("html_url", "").strip()
    if not title or not url:
        return None
    return RawArticle(
        title=title,
        url=url,
        source="github_trends",
        description_snippet=(item.get("description") or "").strip(),
        stars=int(item.get("stargazers_count", 0) or 0),
    )


def fetch_github_trends(limit: int = DEFAULT_LIMIT) -> list[RawArticle]:
    week_ago = (datetime.now(UTC) - timedelta(days=7)).strftime("%Y-%m-%d")
    month_ago = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")

    articles: list[RawArticle] = []
    seen_urls: set[str] = set()

    for label, query_template, sort in SEARCH_QUERY_SPECS:
        if len(articles) >= limit:
            break

        query = query_template.format(week_ago=week_ago, month_ago=month_ago)
        try:
            items = _search_repositories(query, sort, PER_QUERY_LIMIT)
        except requests.RequestException as exc:
            logger.warning("GitHub search failed (%s): %s", label, exc)
            continue

        for item in items:
            article = _repo_to_article(item)
            if article is None or article.url in seen_urls:
                continue
            seen_urls.add(article.url)
            articles.append(article)
            if len(articles) >= limit:
                break

    return articles
