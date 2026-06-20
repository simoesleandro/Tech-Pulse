"""Testes para geração de digest."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.digest import build_digest_payload, _source_label
from app.models import NewsItem


def _make_item(**kwargs) -> MagicMock:
    defaults = {
        "id": 1,
        "title": "Article PT",
        "title_original": "Article EN",
        "url": "https://example.com",
        "source": "hacker_news",
        "description": "Description",
        "ai_reasoning": "This is relevant",
        "hype_score": 3,
        "ai_relevance": "RELEVANTE",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    item = MagicMock(spec=NewsItem)
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


def test_build_digest_payload_structure():
    item = _make_item()
    payload = build_digest_payload([item], days=7)
    assert "articles" in payload
    assert "slack_text" in payload
    assert "article_count" in payload
    assert payload["article_count"] == 1


def test_build_digest_payload_empty():
    payload = build_digest_payload([], days=7)
    assert payload["article_count"] == 0
    assert payload["articles"] == []


def test_slack_text_contains_title():
    item = _make_item(title="Python 3.13 Released")
    payload = build_digest_payload([item], days=7)
    assert "Python 3.13 Released" in payload["slack_text"]


def test_source_label_rss():
    assert _source_label("rss/cloudflare-blog") == "Cloudflare Blog"


def test_source_label_known():
    assert _source_label("hacker_news") == "Hacker News"


def test_source_label_unknown():
    assert _source_label("unknown_source") == "unknown_source"
