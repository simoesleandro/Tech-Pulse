import logging
import re

import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services.hype import compute_hype_score
from app.services.scrapers.base import RawArticle

logger = logging.getLogger(__name__)

GITHUB_REPO_PATTERN = re.compile(r"github\.com/([^/]+)/([^/?#]+)")
DEVTO_ARTICLE_PATTERN = re.compile(r"dev\.to/([^/]+)/([^/?#]+)")
GITHUB_USER_AGENT = "Mozilla/5.0 (compatible; TechPulseBot/1.0)"


def _fetch_github_stars(owner: str, repo: str) -> int:
    response = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers={"Accept": "application/vnd.github+json", "User-Agent": GITHUB_USER_AGENT},
        timeout=12,
    )
    if response.status_code != 200:
        return 0
    return int(response.json().get("stargazers_count", 0) or 0)


def _fetch_devto_engagement(username: str, slug: str) -> tuple[int, int]:
    response = requests.get(
        f"https://dev.to/api/articles/{username}/{slug}",
        timeout=12,
    )
    if response.status_code != 200:
        return 0, 0
    data = response.json()
    return (
        int(data.get("positive_reactions_count", 0) or 0),
        int(data.get("comments_count", 0) or 0),
    )


def item_to_raw_article(item: NewsItem) -> RawArticle:
    return RawArticle(
        title=item.title_original or item.title,
        url=item.url,
        source=item.source,
        description_snippet=item.description,
        positive_reactions=item.engagement_reactions or 0,
        comments_count=item.engagement_comments or 0,
        stars=item.engagement_stars or 0,
        ups=item.engagement_ups or 0,
    )


def apply_engagement_from_article(item: NewsItem, article: RawArticle) -> None:
    item.engagement_reactions = article.positive_reactions
    item.engagement_comments = article.comments_count
    item.engagement_stars = article.stars
    item.engagement_ups = article.ups


def resolve_hype_score(parsed_hype: int, article: RawArticle) -> int:
    computed = compute_hype_score(article)
    return max(parsed_hype, computed)


def _refresh_engagement_metrics(item: NewsItem) -> None:
    if item.source == "github_trends" and not (item.engagement_stars or 0):
        match = GITHUB_REPO_PATTERN.search(item.url)
        if match:
            item.engagement_stars = _fetch_github_stars(match.group(1), match.group(2))

    if item.source == "dev.to" and not (
        (item.engagement_reactions or 0) or (item.engagement_comments or 0)
    ):
        match = DEVTO_ARTICLE_PATTERN.search(item.url)
        if match:
            reactions, comments = _fetch_devto_engagement(match.group(1), match.group(2))
            item.engagement_reactions = reactions
            item.engagement_comments = comments


def refresh_item_hype(item: NewsItem) -> int:
    _refresh_engagement_metrics(item)
    article = item_to_raw_article(item)
    item.hype_score = resolve_hype_score(item.hype_score, article)
    return item.hype_score


def backfill_missing_hype(db: Session, limit: int = 50) -> int:
    items = db.scalars(
        select(NewsItem)
        .where(NewsItem.hype_score == 0)
        .order_by(NewsItem.created_at.desc())
        .limit(limit)
    ).all()

    updated = 0
    for item in items:
        try:
            refresh_item_hype(item)
            updated += 1
        except Exception as exc:
            logger.warning("Hype backfill failed for %s: %s", item.url, exc)

    if updated:
        db.commit()
    return updated
