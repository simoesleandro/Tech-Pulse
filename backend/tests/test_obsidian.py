import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from app.models import NewsItem
from app.services import obsidian as obsidian_service
from app.services.obsidian_agent import ObsidianNoteResult, agente_obsidian, fallback_obsidian_body


def _sample_item(**overrides) -> NewsItem:
    defaults = {
        "id": 7,
        "title": "Teste PT",
        "title_original": "Test EN",
        "description": "Resumo curto sobre Python async.",
        "url": "https://example.com/x",
        "source": "dev.to",
        "ai_relevance": "RELEVANTE",
        "hype_score": 4,
        "ai_reasoning": "Novidade 2 · Utilidade 4 · Comunidade 3 — Guia prático.",
        "is_enriched": True,
        "is_read": False,
        "is_bookmarked": False,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return NewsItem(**defaults)


def test_slugify_title():
    assert obsidian_service.slugify_title("Hello World!") == "hello-world"
    assert obsidian_service.slugify_title("Orquestrador de Agentes") == "orquestrador-de-agentes"


def test_fallback_obsidian_body_uses_callouts():
    note = fallback_obsidian_body(_sample_item())
    body = note.body
    assert "> [!abstract] O que é" in body
    assert "> [!important]" in body or "> [!tip]" in body
    assert "## Conceitos para linkar" in body


def test_news_item_to_markdown_includes_frontmatter():
    note = fallback_obsidian_body(_sample_item())
    markdown = obsidian_service.build_obsidian_note(
        _sample_item(),
        note.body,
        note_title=note.note_title,
        folder=note.folder,
        moc=note.moc,
    )
    assert "techpulse_id: 7" in markdown
    assert "> [!abstract] O que é" in markdown


def test_build_obsidian_note_combines_frontmatter_and_body():
    body = "# Título\n\n> [!info] Teste"
    note = obsidian_service.build_obsidian_note(
        _sample_item(), body, note_title="Título refinado", folder="ia-llms", moc="MOC-IA-LLMs"
    )
    assert "area:" in note
    assert note.startswith("---")
    assert "# Título" in note


def test_agente_obsidian_falls_back_on_invalid_response():
    item = _sample_item()

    with patch(
        "app.services.obsidian_agent.fetch_article_context",
        return_value=("contexto mínimo", 0),
    ), patch(
        "app.services.obsidian_agent.ollama_generate",
        new_callable=AsyncMock,
        side_effect=["resumo\n- ponto", "resposta inválida sem json"],
    ), patch(
        "app.services.obsidian_agent.agente_orquestrador_obsidian",
        new_callable=AsyncMock,
        side_effect=lambda item, analysis: merge_orchestration(
            analysis, fallback_orchestration(item, analysis)
        ),
    ):
        from app.services.obsidian_orchestrator import fallback_orchestration, merge_orchestration

        note = asyncio.run(agente_obsidian(item))

    assert "> [!abstract] O que é" in note.body


def test_export_items_filesystem_uses_agent(monkeypatch):
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_REST_API_KEY", "")
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        item = _sample_item(id=3, title="Python tips")

        agent_body = """# Python tips

> [!abstract] O que é
> Guia sobre dicas de Python.

## Desenvolvimento

### Performance
- Use list comprehensions

> [!tip] Takeaways práticos
> - Profile antes de otimizar

## Conceitos para linkar

- [[Python]]

> [!info] Avaliação Tech-Pulse
> **Hype:** 3/5

---

[Fonte original](https://example.com/py)
"""

        with patch(
            "app.services.obsidian.generate_obsidian_note",
            new=AsyncMock(
                return_value=ObsidianNoteResult(
                    body=agent_body,
                    note_title="Python tips",
                    folder="python-backend",
                    moc="MOC-Python",
                )
            ),
        ):
            result = asyncio.run(obsidian_service.export_items_to_obsidian([item]))

        assert result["exported"] == 1
        assert result["exported_ids"] == [3]
        assert result["mode"] == "filesystem"

        written = tmp_path / "Tech-Pulse" / "python-backend" / "3-python-tips.md"
        content = written.read_text(encoding="utf-8")
        assert "> [!abstract] O que é" in content
        assert "techpulse_id: 3" in content
        assert "[[Python]]" in content


def test_export_items_hybrid_writes_filesystem_without_rest(monkeypatch):
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_REST_API_KEY", "test-key")
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", tmp_dir)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")
        monkeypatch.setattr(
            obsidian_service,
            "check_rest_connection",
            lambda: (False, "REST offline"),
        )

        item = _sample_item(id=4, title="Hybrid note")
        agent_body = "# Hybrid\n\n> [!abstract] O que é\n> Teste híbrido.\n"

        with patch(
            "app.services.obsidian.generate_obsidian_note",
            new=AsyncMock(
                return_value=ObsidianNoteResult(
                    body=agent_body,
                    note_title="Hybrid note",
                    folder="geral",
                    moc="MOC-Tech-Pulse",
                )
            ),
        ):
            result = asyncio.run(obsidian_service.export_items_to_obsidian([item]))

        assert result["exported"] == 1
        assert result["mode"] == "hybrid"
        written = Path(tmp_dir) / "Tech-Pulse" / "4-hybrid-note.md"
        assert written.is_file()
