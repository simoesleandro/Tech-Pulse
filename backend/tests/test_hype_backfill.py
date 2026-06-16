from unittest.mock import patch

from app.services.hype_backfill import _fetch_devto_engagement, refresh_item_hype, resolve_hype_score
from app.services.scrapers.base import RawArticle


def test_resolve_hype_prefers_computed_when_model_returns_zero():
    article = RawArticle(
        title="popular/repo",
        url="https://github.com/popular/repo",
        source="github_trends",
        stars=12000,
    )

    assert resolve_hype_score(0, article) >= 4


def test_resolve_hype_blends_model_and_engagement():
    article = RawArticle(
        title="Mid impact post",
        url="https://dev.to/example/mid",
        source="dev.to",
        positive_reactions=10,
        comments_count=3,
    )

    assert resolve_hype_score(3, article) in {2, 3, 4}


def test_devto_engagement_fetch_parses_counts():
    with patch("app.services.hype_backfill.requests.get") as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "positive_reactions_count": 42,
            "comments_count": 8,
        }

        reactions, comments = _fetch_devto_engagement("author", "my-post")

    assert reactions == 42
    assert comments == 8


def test_refresh_item_hype_for_devto():
    from app.models import NewsItem

    item = NewsItem(
        title="Post dev.to",
        title_original="Dev post",
        description="Resumo",
        url="https://dev.to/author/my-post",
        source="dev.to",
        ai_relevance="RELEVANTE",
        hype_score=0,
    )

    with patch("app.services.hype_backfill._fetch_devto_engagement", return_value=(50, 10)):
        score = refresh_item_hype(item)

    assert item.engagement_reactions == 50
    assert item.engagement_comments == 10
    assert score >= 3
