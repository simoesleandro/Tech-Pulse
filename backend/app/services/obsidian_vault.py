"""Utilitários do vault Obsidian: stubs MOC e migração de layout legado."""

from __future__ import annotations

import logging
import os
import re
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services import obsidian as obsidian_service
from app.services.obsidian_orchestrator import (
    KNOWLEDGE_FOLDERS,
    folder_display_name,
    folder_slug_from_area_label,
    folder_slug_from_moc,
    infer_folder_from_text,
    moc_for_folder,
)
from app.services.obsidian_titles import prettify_note_title

logger = logging.getLogger(__name__)

MOC_INDEX_FOLDER = "📚 Índices"
MOC_ROOT_NAME = "MOC-Tech-Pulse"

LEGACY_KEBAB_FILE = re.compile(r"^(\d+)-(.+)\.md$", re.IGNORECASE)
MODERN_FILE = re.compile(r"^\d+ - .+\.md$", re.IGNORECASE)
TECHPULSE_ID_PATTERN = re.compile(r"^techpulse_id:\s*(\d+)\s*$", re.MULTILINE)
TITLE_FM_PATTERN = re.compile(r'^title:\s*["\']?(.+?)["\']?\s*$', re.MULTILINE)
AREA_FM_PATTERN = re.compile(r'^area:\s*["\']?([^"\n]+)["\']?\s*$', re.MULTILINE)
MOC_FM_PATTERN = re.compile(r'^moc:\s*["\']?([^"\n]+)["\']?\s*$', re.MULTILINE)
MODERN_KEBAB_FILE = re.compile(r"^(\d+) - ([a-z0-9]+(?:-[a-z0-9]+)+)\.md$", re.IGNORECASE)
ROOT_NOTE_FILE = re.compile(r"^(\d+) - .+\.md$", re.IGNORECASE)


def moc_catalog() -> list[tuple[str, str, str]]:
    """(nome_moc, rótulo_área, slug_pasta)"""
    entries = [
        (moc_for_folder(slug), folder_display_name(slug), slug)
        for slug in KNOWLEDGE_FOLDERS
        if slug != "geral"
    ]
    entries.append((MOC_ROOT_NAME, folder_display_name("geral"), "geral"))
    return entries


def _moc_relative_path(moc_name: str) -> str:
    return f"{obsidian_service.OBSIDIAN_FOLDER}/{MOC_INDEX_FOLDER}/{moc_name}.md"


def _folder_notes_path(folder_slug: str) -> str:
    return f"{obsidian_service.OBSIDIAN_FOLDER}/{folder_display_name(folder_slug)}"


def build_moc_stub(moc_name: str, area_label: str, folder_slug: str) -> str:
    notes_path = _folder_notes_path(folder_slug)
    parent_link = f"[[{MOC_ROOT_NAME}|← Índice geral Tech-Pulse]]"
    if moc_name == MOC_ROOT_NAME:
        areas = "\n".join(
            f"- [[{name}]] — {label}"
            for name, label, _slug in moc_catalog()
            if name != MOC_ROOT_NAME
        )
        body = f"""# {area_label}

Mapa de conteúdo das notas importadas pelo **Tech-Pulse**.

## Áreas

{areas}

## Todas as notas Tech-Pulse

```dataview
LIST
FROM "{obsidian_service.OBSIDIAN_FOLDER}"
WHERE techpulse_id
SORT file.name ASC
```
"""
    else:
        body = f"""# {area_label}

Índice desta área — notas curadas pelo **Tech-Pulse**.

{parent_link}

## Notas nesta área

```dataview
LIST
FROM "{notes_path}"
WHERE techpulse_id
SORT file.name ASC
```
"""
    return f"""---
title: "{area_label}"
tags: [moc, tech-pulse]
type: moc
---

{body}
"""


def _vault_root() -> Path:
    obsidian_service._reload_settings()
    root = Path(obsidian_service.OBSIDIAN_VAULT_PATH)
    if not root.is_dir():
        raise RuntimeError(f"OBSIDIAN_VAULT_PATH inválido: {obsidian_service.OBSIDIAN_VAULT_PATH}")
    return root


def ensure_moc_stubs() -> dict[str, int | list[str]]:
    """Cria ou atualiza arquivos MOC no vault (somente filesystem)."""
    root = _vault_root()
    created = 0
    updated = 0
    paths: list[str] = []

    for moc_name, area_label, folder_slug in moc_catalog():
        relative = _moc_relative_path(moc_name)
        destination = root / relative.replace("/", os.sep)
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = build_moc_stub(moc_name, area_label, folder_slug)
        existed = destination.is_file()
        destination.write_text(content, encoding="utf-8")
        paths.append(relative)
        if existed:
            updated += 1
        else:
            created += 1

    return {"created": created, "updated": updated, "paths": paths}


def _parse_item_id_from_file(path: Path) -> int | None:
    legacy = LEGACY_KEBAB_FILE.match(path.name)
    if legacy:
        return int(legacy.group(1))
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = TECHPULSE_ID_PATTERN.search(content)
    return int(match.group(1)) if match else None


def _title_from_legacy_slug(slug_part: str) -> str:
    return slug_part.replace("-", " ").strip().title()


def _resolve_note_title(path: Path, item: NewsItem | None, legacy_slug: str | None) -> str:
    if item and item.title:
        return prettify_note_title(item.title)
    try:
        content = path.read_text(encoding="utf-8")
        fm = TITLE_FM_PATTERN.search(content)
        if fm:
            return prettify_note_title(fm.group(1).strip())
    except OSError:
        pass
    if legacy_slug:
        return prettify_note_title(_title_from_legacy_slug(legacy_slug))
    stem = path.stem
    if " - " in stem:
        return prettify_note_title(stem.split(" - ", 1)[1].strip())
    return prettify_note_title(stem)


def _legacy_folder_slug(path: Path, tech_pulse_root: Path) -> str | None:
    try:
        relative = path.parent.relative_to(tech_pulse_root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    first = relative.parts[0]
    if first in KNOWLEDGE_FOLDERS:
        return first
    return None


def _resolve_folder_slug(path: Path, content: str, item: NewsItem | None) -> str:
    area_match = AREA_FM_PATTERN.search(content)
    if area_match:
        slug = folder_slug_from_area_label(area_match.group(1).strip())
        if slug:
            return slug

    moc_match = MOC_FM_PATTERN.search(content)
    if moc_match:
        slug = folder_slug_from_moc(moc_match.group(1).strip())
        if slug:
            return slug

    if item:
        return infer_folder_from_text(f"{item.title} {item.description or ''}")

    return infer_folder_from_text(f"{path.stem}\n{content[:800]}")


def _patch_frontmatter_area(content: str, folder_slug: str) -> str:
    area_label = folder_display_name(folder_slug)
    moc_name = moc_for_folder(folder_slug)
    if AREA_FM_PATTERN.search(content):
        content = AREA_FM_PATTERN.sub(f'area: "{area_label}"', content, count=1)
    elif content.startswith("---"):
        content = content.replace("---\n", f'---\narea: "{area_label}"\n', 1)
    if MOC_FM_PATTERN.search(content):
        content = MOC_FM_PATTERN.sub(f'moc: "{moc_name}"', content, count=1)
    elif area_label in content:
        content = re.sub(
            rf'(area:\s*"?{re.escape(area_label)}"?\s*\n)',
            rf'\1moc: "{moc_name}"\n',
            content,
            count=1,
        )
    return content


def organize_loose_vault_notes(db: Session) -> dict[str, int | list[str]]:
    """Move notas soltas na raiz de Tech-Pulse para a pasta de área correta."""
    root = _vault_root()
    tech_pulse = root / obsidian_service.OBSIDIAN_FOLDER
    if not tech_pulse.is_dir():
        return {"organized": 0, "skipped": 0, "errors": []}

    organized = 0
    skipped = 0
    errors: list[str] = []

    for path in list(tech_pulse.glob("*.md")):
        if path.name.startswith("."):
            skipped += 1
            continue
        if not ROOT_NOTE_FILE.match(path.name):
            skipped += 1
            continue

        item_id = int(path.name.split(" - ", 1)[0])
        item = db.get(NewsItem, item_id)
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")
            continue

        folder_slug = _resolve_folder_slug(path, content, item)
        note_title = _resolve_note_title(path, item, None)
        new_relative = obsidian_service.build_note_relative_path(
            item_id=item_id,
            note_title=note_title,
            folder_slug=folder_slug,
        )
        new_path = root / new_relative.replace("/", os.sep)

        if path.resolve() == new_path.resolve():
            skipped += 1
            continue
        if new_path.exists():
            errors.append(f"{path.name}: destino já existe ({new_relative})")
            skipped += 1
            continue

        try:
            updated = _patch_frontmatter_area(content, folder_slug)
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text(updated, encoding="utf-8")
            path.unlink()
            organized += 1
            logger.info("Organized %s → %s", path.name, new_relative)
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")

    return {"organized": organized, "skipped": skipped, "errors": errors}


def migrate_legacy_vault_layout(db: Session) -> dict[str, int | list[str]]:
    """Move notas kebab-case de pastas slug para layout legível."""
    root = _vault_root()
    tech_pulse = root / obsidian_service.OBSIDIAN_FOLDER
    if not tech_pulse.is_dir():
        return {"migrated": 0, "skipped": 0, "errors": [], "removed_empty_dirs": 0, "retitled": 0, "organized": 0}

    migrated = 0
    skipped = 0
    errors: list[str] = []
    candidates: list[Path] = []

    for path in tech_pulse.rglob("*.md"):
        if MOC_INDEX_FOLDER in path.parts:
            continue
        if MODERN_FILE.match(path.name):
            skipped += 1
            continue
        if LEGACY_KEBAB_FILE.match(path.name):
            candidates.append(path)

    item_ids = [i for p in candidates if (i := _parse_item_id_from_file(p)) is not None]
    items_by_id: dict[int, NewsItem] = {}
    if item_ids:
        rows = db.scalars(select(NewsItem).where(NewsItem.id.in_(item_ids))).all()
        items_by_id = {row.id: row for row in rows}

    for path in candidates:
        item_id = _parse_item_id_from_file(path)
        if item_id is None:
            skipped += 1
            continue

        item = items_by_id.get(item_id)
        legacy_match = LEGACY_KEBAB_FILE.match(path.name)
        legacy_slug_part = legacy_match.group(2) if legacy_match else None
        folder_slug = _legacy_folder_slug(path, tech_pulse) or "geral"
        if item:
            folder_slug = _infer_folder_from_item(item, folder_slug)

        note_title = _resolve_note_title(path, item, legacy_slug_part)
        new_relative = obsidian_service.build_note_relative_path(
            item_id=item_id,
            note_title=note_title,
            folder_slug=folder_slug,
        )
        new_path = root / new_relative.replace("/", os.sep)

        if path.resolve() == new_path.resolve():
            skipped += 1
            continue
        if new_path.exists():
            errors.append(f"{path.name}: destino já existe ({new_relative})")
            skipped += 1
            continue

        try:
            new_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(new_path))
            migrated += 1
            logger.info("Migrated %s → %s", path, new_relative)
        except OSError as exc:
            errors.append(f"{path.name}: {exc}")

    removed_dirs = _remove_empty_legacy_dirs(tech_pulse)
    retitled = _retitle_modern_kebab_files(root, db, tech_pulse)
    organized = organize_loose_vault_notes(db)

    return {
        "migrated": migrated,
        "skipped": skipped,
        "errors": errors,
        "removed_empty_dirs": removed_dirs,
        "retitled": retitled,
        "organized": organized["organized"],
    }


def _infer_folder_from_item(item: NewsItem, fallback: str) -> str:
    return infer_folder_from_text(f"{item.title} {item.description or ''}", fallback)


def _retitle_modern_kebab_files(root: Path, db: Session, tech_pulse: Path) -> int:
    """Renomeia notas já no formato novo mas com título slug (ex: awesome-selfhosted)."""
    retitled = 0
    for path in tech_pulse.rglob("*.md"):
        if MOC_INDEX_FOLDER in path.parts:
            continue
        match = MODERN_KEBAB_FILE.match(path.name)
        if not match:
            continue
        item_id = int(match.group(1))
        item = db.get(NewsItem, item_id)
        folder_slug = _legacy_folder_slug(path, tech_pulse)
        pretty = prettify_note_title(item.title if item else match.group(2).replace("-", " "))
        new_relative = obsidian_service.build_note_relative_path(
            item_id=item_id,
            note_title=pretty,
            folder_slug=folder_slug or "geral",
        )
        new_path = root / new_relative.replace("/", os.sep)
        if path.resolve() == new_path.resolve():
            continue
        if new_path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8")
            content = TITLE_FM_PATTERN.sub(f'title: "{pretty}"', content, count=1)
            new_path.parent.mkdir(parents=True, exist_ok=True)
            new_path.write_text(content, encoding="utf-8")
            path.unlink()
            retitled += 1
        except OSError as exc:
            logger.warning("Retitle failed for %s: %s", path, exc)
    return retitled


def _remove_empty_legacy_dirs(tech_pulse: Path) -> int:
    removed = 0
    for slug in KNOWLEDGE_FOLDERS:
        legacy_dir = tech_pulse / slug
        if legacy_dir.is_dir() and not any(legacy_dir.rglob("*")):
            try:
                legacy_dir.rmdir()
                removed += 1
            except OSError:
                pass
    return removed
