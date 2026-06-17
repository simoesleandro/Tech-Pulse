from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import NewsItem
from app.services import obsidian as obsidian_service
from app.services.obsidian_titles import prettify_note_title
from app.services.obsidian_vault import (
    MOC_INDEX_FOLDER,
    MOC_ROOT_NAME,
    build_moc_stub,
    ensure_moc_stubs,
    migrate_legacy_vault_layout,
    organize_loose_vault_notes,
)


def test_prettify_github_repo_slug():
    assert prettify_note_title("awesome-selfhosted") == "Awesome Selfhosted"
    assert prettify_note_title("torvalds/linux") == "Torvalds/linux"
    assert prettify_note_title("Deploy do Gemma 12B") == "Deploy do Gemma 12B"


def test_build_moc_stub_includes_dataview():
    content = build_moc_stub("MOC-IA-LLMs", "🤖 IA & LLMs", "ia-llms")
    assert "MOC-IA-LLMs" in content or "🤖 IA & LLMs" in content
    assert "```dataview" in content
    assert MOC_ROOT_NAME in content


def test_ensure_moc_stubs_creates_index_files(monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", tmp_dir)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        result = ensure_moc_stubs()
        assert result["created"] >= 9
        root_moc = Path(tmp_dir) / "Tech-Pulse" / MOC_INDEX_FOLDER / f"{MOC_ROOT_NAME}.md"
        ia_moc = Path(tmp_dir) / "Tech-Pulse" / MOC_INDEX_FOLDER / "MOC-IA-LLMs.md"
        assert root_moc.is_file()
        assert ia_moc.is_file()

        result2 = ensure_moc_stubs()
        assert result2["updated"] >= 9
        assert result2["created"] == 0


def test_migrate_legacy_kebab_note(db_session, monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", tmp_dir)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        item = NewsItem(
            title="Após a IA assumir tudo",
            title_original="After AI takes over",
            description="Artigo sobre IA",
            url="https://example.com/ia",
            source="dev.to",
            ai_relevance="RELEVANTE",
            hype_score=5,
            is_enriched=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        legacy_dir = Path(tmp_dir) / "Tech-Pulse" / "ia-llms"
        legacy_dir.mkdir(parents=True)
        legacy_file = legacy_dir / f"{item.id}-apos-a-ia-assumir-tudo.md"
        legacy_file.write_text(
            f"---\ntechpulse_id: {item.id}\ntitle: Após a IA assumir tudo\n---\n# Old",
            encoding="utf-8",
        )

        result = migrate_legacy_vault_layout(db_session)
        assert result["migrated"] == 1
        assert not legacy_file.exists()

        new_file = (
            Path(tmp_dir)
            / "Tech-Pulse"
            / "🤖 IA & LLMs"
            / f"{item.id} - Após a IA assumir tudo.md"
        )
        assert new_file.is_file()
        assert not legacy_dir.exists()


def test_organize_loose_root_note(db_session, monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", tmp_dir)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        item = NewsItem(
            title="awesome-selfhosted",
            title_original="awesome-selfhosted",
            description="Lista de software self-hosted",
            url="https://github.com/awesome-selfhosted",
            source="github_trends",
            ai_relevance="RELEVANTE",
            hype_score=4,
            is_enriched=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        root_note = Path(tmp_dir) / "Tech-Pulse" / f"{item.id} - Awesome Selfhosted.md"
        root_note.parent.mkdir(parents=True)
        root_note.write_text(
            f'---\ntitle: "Awesome Selfhosted"\ntechpulse_id: {item.id}\n---\n# Note',
            encoding="utf-8",
        )

        result = organize_loose_vault_notes(db_session)
        assert result["organized"] == 1
        target = Path(tmp_dir) / "Tech-Pulse" / "⚡ Ferramentas & Produtividade" / f"{item.id} - Awesome Selfhosted.md"
        assert target.is_file()
        assert not root_note.exists()


def test_migrate_skips_modern_filenames(db_session, monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", tmp_dir)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        modern = Path(tmp_dir) / "Tech-Pulse" / "🤖 IA & LLMs"
        modern.mkdir(parents=True)
        note = modern / "9 - Deploy do Gemma 12B.md"
        note.write_text("# ok", encoding="utf-8")

        result = migrate_legacy_vault_layout(db_session)
        assert result["migrated"] == 0
        assert result["skipped"] >= 1
        assert note.is_file()
