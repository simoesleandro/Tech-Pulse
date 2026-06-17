from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.models import NewsItem
from app.services import obsidian as obsidian_service
from app.services.obsidian_backfill import (
    _discover_from_filesystem,
    _parse_ids_from_markdown,
    backfill_obsidian_exports,
)


def test_parse_ids_from_markdown():
    content = """---
techpulse_id: 42
title: Test
---
# Body
"""
    assert _parse_ids_from_markdown(content) == {42}


def test_discover_from_filesystem_by_filename(monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        folder = tmp_path / "Tech-Pulse"
        folder.mkdir()
        note = folder / "12-python-async.md"
        note.write_text("---\ntitle: x\n---\n# Note", encoding="utf-8")

        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        discovered = _discover_from_filesystem()
        assert 12 in discovered
        assert discovered[12].tzinfo is not None


def test_backfill_obsidian_exports_updates_db(db_session, monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        folder = tmp_path / "Tech-Pulse"
        folder.mkdir()

        item = NewsItem(
            title="Legacy",
            title_original="Legacy",
            description="Desc",
            url="https://example.com/legacy",
            source="dev.to",
            ai_relevance="RELEVANTE",
            hype_score=3,
            is_enriched=True,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        (folder / f"{item.id}-legacy-note.md").write_text(
            f"---\ntechpulse_id: {item.id}\n---\n# Legacy",
            encoding="utf-8",
        )

        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        result = backfill_obsidian_exports(db_session)
        assert result["discovered"] == 1
        assert result["updated"] == 1

        db_session.refresh(item)
        assert item.obsidian_exported_at is not None


def test_backfill_obsidian_skips_already_marked(db_session, monkeypatch):
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        folder = tmp_path / "Tech-Pulse"
        folder.mkdir()
        (folder / "8-note.md").write_text("# x", encoding="utf-8")

        exported_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        item = NewsItem(
            id=8,
            title="Marked",
            title_original="Marked",
            description="Desc",
            url="https://example.com/8",
            source="dev.to",
            ai_relevance="RELEVANTE",
            hype_score=3,
            is_enriched=True,
            obsidian_exported_at=exported_at,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(item)
        db_session.commit()

        monkeypatch.setattr(obsidian_service, "_reload_settings", lambda: None)
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_VAULT_PATH", str(tmp_path))
        monkeypatch.setattr(obsidian_service, "OBSIDIAN_FOLDER", "Tech-Pulse")

        result = backfill_obsidian_exports(db_session)
        assert result["already_marked"] == 1
        assert result["updated"] == 0
