import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services import obsidian as obsidian_service

logger = logging.getLogger(__name__)

NOTE_FILENAME_PATTERN = re.compile(r"^(\d+)-.+\.md$", re.IGNORECASE)
TECHPULSE_ID_PATTERN = re.compile(r"^techpulse_id:\s*(\d+)\s*$", re.MULTILINE)


def _parse_ids_from_markdown(content: str) -> set[int]:
    return {int(match) for match in TECHPULSE_ID_PATTERN.findall(content)}


def _discover_from_filesystem() -> dict[int, datetime]:
    obsidian_service._reload_settings()
    vault_path = obsidian_service.OBSIDIAN_VAULT_PATH
    folder_name = obsidian_service.OBSIDIAN_FOLDER

    if not vault_path:
        return {}

    folder = Path(vault_path) / folder_name.replace("/", os.sep).replace("\\", os.sep)
    if not folder.is_dir():
        logger.warning("Obsidian backfill: pasta não encontrada %s", folder)
        return {}

    discovered: dict[int, datetime] = {}
    for path in folder.rglob("*.md"):
        item_ids: set[int] = set()

        filename_match = NOTE_FILENAME_PATTERN.match(path.name)
        if filename_match:
            item_ids.add(int(filename_match.group(1)))

        try:
            content = path.read_text(encoding="utf-8")
            item_ids.update(_parse_ids_from_markdown(content))
        except OSError as exc:
            logger.warning("Obsidian backfill: falha ao ler %s: %s", path, exc)

        if not item_ids:
            continue

        exported_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        for item_id in item_ids:
            discovered[item_id] = max(discovered.get(item_id, exported_at), exported_at)

    return discovered


def _note_exists_via_rest(relative_path: str) -> bool:
    obsidian_service._reload_settings()
    if not obsidian_service.OBSIDIAN_REST_API_KEY:
        return False

    headers = {"Authorization": f"Bearer {obsidian_service.OBSIDIAN_REST_API_KEY}"}
    try:
        with httpx.Client(verify=obsidian_service.OBSIDIAN_VERIFY_SSL, timeout=8.0) as client:
            response = client.get(
                obsidian_service._vault_file_url(relative_path),
                headers=headers,
            )
            return response.status_code == 200
    except Exception as exc:
        logger.debug("Obsidian REST probe failed for %s: %s", relative_path, exc)
        return False


def _discover_via_rest_probe(db: Session) -> dict[int, datetime]:
    if obsidian_service.get_obsidian_mode() != "rest":
        return {}

    candidates = db.scalars(
        select(NewsItem)
        .where(NewsItem.obsidian_exported_at.is_(None))
        .order_by(NewsItem.created_at.desc())
    ).all()

    discovered: dict[int, datetime] = {}
    now = datetime.now(timezone.utc)
    for item in candidates:
        if _note_exists_via_rest(obsidian_service.note_relative_path(item)):
            discovered[item.id] = now
    return discovered


def discover_obsidian_exports(db: Session) -> dict[int, datetime]:
    obsidian_service._reload_settings()
    discovered = _discover_from_filesystem()
    if discovered:
        return discovered
    return _discover_via_rest_probe(db)


def backfill_obsidian_exports(db: Session) -> dict:
    discovered = discover_obsidian_exports(db)

    updated = 0
    already_marked = 0
    missing_in_db = 0

    for item_id, exported_at in discovered.items():
        item = db.get(NewsItem, item_id)
        if item is None:
            missing_in_db += 1
            continue
        if item.obsidian_exported_at is not None:
            already_marked += 1
            continue
        item.obsidian_exported_at = exported_at
        updated += 1

    if updated:
        db.commit()
    else:
        db.rollback()

    return {
        "discovered": len(discovered),
        "updated": updated,
        "already_marked": already_marked,
        "missing_in_db": missing_in_db,
    }
