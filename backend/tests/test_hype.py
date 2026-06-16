from app.services.scrapers.base import RawArticle
from app.services.hype import compute_hype_score


def test_hype_score_devto():
    article = RawArticle(
        title="Test",
        url="https://example.com",
        source="dev.to",
        positive_reactions=40,
        comments_count=10,
    )
    assert compute_hype_score(article) == 5


def test_hype_score_github():
    article = RawArticle(
        title="repo",
        url="https://github.com/x/y",
        source="github_trends",
        stars=10000,
    )
    assert compute_hype_score(article) >= 3
