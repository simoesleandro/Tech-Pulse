"""Testes para o endpoint RSS output feed."""
import types
import pytest
from xml.etree.ElementTree import fromstring

from app.routes.feed import build_rss_feed, _rfc822, _sanitize
from app.models import NewsItem
from datetime import datetime, timezone


def _make_item(**kwargs) -> types.SimpleNamespace:
    """Cria um item sintético compatível com build_rss_feed (duck typing)."""
    defaults = {
        "id": 1,
        "title": "Test Article",
        "title_original": "Test Article",
        "url": "https://example.com/test",
        "source": "hacker_news",
        "description": "A test article",
        "ai_reasoning": "This is relevant because...",
        "hype_score": 3,
        "ai_relevance": "RELEVANTE",
        "is_read": False,
        "is_bookmarked": False,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def test_build_rss_feed_valid_xml():
    item = _make_item()
    xml_bytes = build_rss_feed([item])
    root = fromstring(xml_bytes)  # levanta se XML inválido
    assert root.tag == "rss"


def test_build_rss_feed_has_channel():
    xml_bytes = build_rss_feed([])
    root = fromstring(xml_bytes)
    channel = root.find("channel")
    assert channel is not None


def test_build_rss_feed_item_fields():
    item = _make_item(title="My Article", url="https://example.com/my")
    xml_bytes = build_rss_feed([item])
    root = fromstring(xml_bytes)
    rss_item = root.find("channel/item")
    assert rss_item is not None
    assert rss_item.find("title").text == "My Article"
    assert rss_item.find("link").text == "https://example.com/my"


def test_sanitize_removes_control_chars():
    result = _sanitize("hello\x00world\x1Ftest")
    assert "\x00" not in result
    assert "\x1F" not in result
    assert "helloworld" in result


def test_sanitize_empty():
    assert _sanitize(None) == ""
    assert _sanitize("") == ""


def test_build_rss_empty_list():
    xml_bytes = build_rss_feed([])
    root = fromstring(xml_bytes)
    items = root.findall("channel/item")
    assert items == []
