from datetime import datetime, timezone
from unittest.mock import patch

from app.models import NewsItem
from app.services.ingest import get_backfill_status, needs_agent_refresh, re_enrich_legacy_items
from app.services.scrapers.base import EnrichedArticle


def _item(**overrides) -> NewsItem:
    defaults = {
        "title": "Título PT",
        "title_original": "Title EN",
        "description": "Resumo",
        "url": "https://example.com/a",
        "source": "dev.to",
        "ai_relevance": "RELEVANTE",
        "hype_score": 3,
        "is_enriched": True,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return NewsItem(**defaults)


def test_needs_agent_refresh_detects_legacy_reasoning():
    legacy = _item(ai_reasoning="Artigo interessante sobre Python.")
    modern = _item(ai_reasoning="Novidade 3 · Utilidade 4 · Comunidade 2 — Guia prático.")
    empty = _item(ai_reasoning=None)
    lixo = _item(ai_relevance="LIXO", ai_reasoning="")

    assert needs_agent_refresh(legacy) is True
    assert needs_agent_refresh(empty) is True
    assert needs_agent_refresh(modern) is False
    assert needs_agent_refresh(lixo) is False


def test_get_backfill_status_counts(db_session):
    db_session.add_all(
        [
            _item(url="https://example.com/a", ai_reasoning="Legado sem rubrica"),
            _item(
                url="https://example.com/b",
                ai_reasoning="Novidade 2 · Utilidade 3 · Comunidade 2 — ok",
                obsidian_exported_at=datetime.now(timezone.utc),
            ),
            _item(url="https://example.com/c", ai_relevance="LIXO", ai_reasoning=""),
        ]
    )
    db_session.commit()

    status = get_backfill_status(db_session)
    assert status["legacy_enrichment_pending"] == 1
    assert status["obsidian_unmarked"] == 1


def _mock_enrich(_article, on_agent_progress=None) -> EnrichedArticle:
    return EnrichedArticle(
        ai_relevance="RELEVANTE",
        title_pt="Título reprocessado",
        description_pt="Descrição com nova rubrica.",
        hype_score=4,
        ai_reasoning="Novidade 4 · Utilidade 3 · Comunidade 3 — Atualizado pelos 3 agentes.",
    )


def test_re_enrich_legacy_items_updates_reasoning(db_session):
    item = _item(ai_reasoning="Resumo antigo do Gemma único.")
    db_session.add(item)
    db_session.commit()

    with patch("app.services.ingest.enrich_article_sync", side_effect=_mock_enrich):
        result = re_enrich_legacy_items(db_session, limit=5)

    assert result["processed"] == 1
    assert result["remaining"] == 0

    db_session.refresh(item)
    assert "Novidade" in (item.ai_reasoning or "")
    assert item.title == "Título reprocessado"
