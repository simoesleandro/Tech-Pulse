import pytest
from datetime import datetime, timezone

from app.models import NewsItem
from app.services import obsidian as obsidian_service


def test_slugify_title():
    assert obsidian_service.slugify_title("Hello World!") == "hello-world"
    assert obsidian_service.slugify_title("Orquestrador de Agentes") == "orquestrador-de-agentes"


def test_news_item_to_markdown():
    item = NewsItem(
        id=7,
        title="Teste PT",
        title_original="Test EN",
        description="Resumo curto.",
        url="https://example.com/x",
        source="dev.to",
        ai_relevance="RELEVANTE",
        hype_score=4,
        ai_reasoning="Impacto alto.",
        is_enriched=True,
        is_read=False,
        is_bookmarked=False,
        created_at=datetime.now(timezone.utc),
    )

    markdown = obsidian_service.news_item_to_markdown(item)
    assert "techpulse_id: 7" in markdown
    assert "# Teste PT" in markdown
    assert "Impacto alto." in markdown


def test_export_items_filesystem(tmp_path, monkeypatch):
    monkeypatch.setattr(obsidian_service, "OBSIDIAN_REST_API_KEY", "")
    monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", str(tmp_path))
    monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

    item = NewsItem(
        id=3,
        title="Python tips",
        title_original="Python tips",
        description="Desc.",
        url="https://example.com/py",
        source="dev.to",
        ai_relevance="RELEVANTE",
        hype_score=3,
        is_enriched=True,
        is_read=False,
        is_bookmarked=False,
        created_at=datetime.now(timezone.utc),
    )

    result = obsidian_service.export_items_to_obsidian([item])
    assert result["exported"] == 1
    assert result["mode"] == "filesystem"
    assert len(result["paths"]) == 1

    written = tmp_path / "Tech-Pulse" / "3-python-tips.md"
    assert written.is_file()
    assert "Python tips" in written.read_text(encoding="utf-8")
