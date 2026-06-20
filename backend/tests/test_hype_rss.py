"""Testes para o hype score de fontes RSS."""
import pytest
from datetime import datetime, timezone, timedelta

from app.services.hype import compute_hype_score, _rss_hype
from app.services.scrapers.base import RawArticle


def _rss_article(**kwargs) -> RawArticle:
    defaults = {"title": "t", "url": "u", "source": "rss/test"}
    defaults.update(kwargs)
    return RawArticle(**defaults)


def test_rss_without_metadata_returns_2():
    """Backward compat: RSS sem pub_date ou content_length → score 2."""
    article = _rss_article()
    assert compute_hype_score(article) == 2


def test_rss_fresh_article_gets_bonus():
    """Artigo publicado há menos de 24h recebe bônus."""
    article = _rss_article(pub_date=datetime.now(timezone.utc) - timedelta(hours=6))
    score = compute_hype_score(article)
    assert score > 2


def test_rss_old_article_no_freshness_bonus():
    """Artigo de mais de 24h não recebe bônus de frescor."""
    old_pub = datetime.now(timezone.utc) - timedelta(days=5)
    article = _rss_article(pub_date=old_pub)
    score = compute_hype_score(article)
    assert score == 2


def test_rss_long_article_gets_bonus():
    """Artigo longo (>2000 chars) recebe bônus de substância."""
    article = _rss_article(content_length=3000)
    score = compute_hype_score(article)
    assert score > 2


def test_rss_very_long_article_gets_bigger_bonus():
    """Artigo muito longo (>5000 chars) recebe bônus maior."""
    article = _rss_article(content_length=6000)
    long_score = compute_hype_score(article)
    medium_article = _rss_article(content_length=3000)
    medium_score = compute_hype_score(medium_article)
    assert long_score > medium_score


def test_rss_fresh_and_long_caps_at_5():
    """Score não ultrapassa 5 mesmo com todos os bônus."""
    article = _rss_article(
        pub_date=datetime.now(timezone.utc) - timedelta(hours=1),
        content_length=10000,
    )
    assert compute_hype_score(article) <= 5


def test_non_rss_sources_unchanged():
    """Fórmulas de dev.to, reddit, etc. não mudam."""
    hn = RawArticle(title="t", url="u", source="hacker_news", ups=100)
    score = compute_hype_score(hn)
    assert score > 0
