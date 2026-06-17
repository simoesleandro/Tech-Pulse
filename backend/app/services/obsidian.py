import asyncio
import logging
import os
import re
import unicodedata
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from sqlalchemy import select

from app.models import NewsItem
from app.services.obsidian_agent import (
    ObsidianNoteResult,
    ObsidianProgressCallback,
    agente_obsidian,
    fallback_obsidian_body,
)
from app.services.obsidian_orchestrator import folder_display_name
from app.services.obsidian_titles import humanize_filename, prettify_note_title

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _reload_settings() -> None:
    load_dotenv(_BACKEND_ROOT / ".env", override=True)

    global OBSIDIAN_REST_URL, OBSIDIAN_REST_API_KEY, OBSIDIAN_VAULT_PATH
    global OBSIDIAN_FOLDER, OBSIDIAN_VERIFY_SSL, OBSIDIAN_OPEN_AFTER_EXPORT

    OBSIDIAN_REST_URL = os.getenv("OBSIDIAN_REST_URL", "https://127.0.0.1:27124").rstrip("/")
    OBSIDIAN_REST_API_KEY = os.getenv("OBSIDIAN_REST_API_KEY", "").strip()
    OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    OBSIDIAN_FOLDER = os.getenv("OBSIDIAN_FOLDER", "Tech-Pulse").strip().strip("/\\")
    OBSIDIAN_VERIFY_SSL = os.getenv("OBSIDIAN_VERIFY_SSL", "false").lower() == "true"
    OBSIDIAN_OPEN_AFTER_EXPORT = os.getenv("OBSIDIAN_OPEN_AFTER_EXPORT", "true").lower() == "true"


_reload_settings()


def get_obsidian_mode() -> str | None:
    _reload_settings()
    has_rest = bool(OBSIDIAN_REST_API_KEY)
    has_vault = bool(OBSIDIAN_VAULT_PATH)
    if has_rest and has_vault:
        return "hybrid"
    if has_rest:
        return "rest"
    if has_vault:
        return "filesystem"
    return None


def _vault_is_configured() -> bool:
    return bool(OBSIDIAN_VAULT_PATH) and Path(OBSIDIAN_VAULT_PATH).is_dir()


def get_obsidian_write_mode() -> str | None:
    mode = get_obsidian_mode()
    if mode in ("filesystem", "hybrid"):
        return "filesystem"
    if mode == "rest":
        return "rest"
    return None


def get_obsidian_config() -> dict:
    mode = get_obsidian_mode()
    return {
        "configured": mode is not None,
        "mode": mode,
        "folder": OBSIDIAN_FOLDER,
        "rest_url": OBSIDIAN_REST_URL if mode == "rest" else None,
    }


def slugify_title(title: str, max_len: int = 60) -> str:
    """Legado — kebab-case para compatibilidade com notas antigas no vault."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_text.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:max_len] or "nota"


def _escape_yaml(value: str) -> str:
    return value.replace('"', '\\"')


def _obsidian_tags(item: NewsItem) -> list[str]:
    source_tag = item.source.replace("/", "-").replace(".", "-")
    return ["tech-pulse", source_tag]


def build_obsidian_frontmatter(
    item: NewsItem,
    *,
    note_title: str | None = None,
    folder: str | None = None,
    moc: str | None = None,
    extra_tags: list[str] | None = None,
) -> str:
    tags = _obsidian_tags(item)
    if extra_tags:
        for tag in extra_tags:
            clean = re.sub(r"[^\w-]", "-", tag.strip().lower())
            if clean and clean not in tags:
                tags.append(clean)
    title = _escape_yaml(prettify_note_title(note_title or item.title))
    area_label = folder_display_name(folder) if folder else ""
    area_line = f'area: "{_escape_yaml(area_label)}"\n' if area_label else ""
    moc_line = f'moc: "{_escape_yaml(moc)}"\n' if moc else ""
    return f"""---
title: "{title}"
source: {item.source}
url: {item.url}
hype: {item.hype_score}
tags: [{", ".join(tags)}]
techpulse_id: {item.id}
{area_line}{moc_line}created: {item.created_at.isoformat()}
---
"""


def build_obsidian_note(
    item: NewsItem,
    body: str,
    *,
    note_title: str | None = None,
    folder: str | None = None,
    moc: str | None = None,
    extra_tags: list[str] | None = None,
) -> str:
    frontmatter = build_obsidian_frontmatter(
        item,
        note_title=note_title,
        folder=folder,
        moc=moc,
        extra_tags=extra_tags,
    )
    return f"{frontmatter}\n{body.strip()}\n"


async def generate_obsidian_note(
    item: NewsItem,
    *,
    use_agent: bool = True,
    on_progress: ObsidianProgressCallback | None = None,
) -> ObsidianNoteResult:
    if use_agent:
        return await agente_obsidian(item, on_progress=on_progress)
    return fallback_obsidian_body(item)


async def generate_obsidian_body(
    item: NewsItem,
    *,
    use_agent: bool = True,
    on_progress: ObsidianProgressCallback | None = None,
) -> str:
    note = await generate_obsidian_note(item, use_agent=use_agent, on_progress=on_progress)
    return note.body


def news_item_to_markdown(item: NewsItem) -> str:
    """Compatibilidade síncrona — usa template fallback sem LLM."""
    note = fallback_obsidian_body(item)
    return build_obsidian_note(
        item,
        note.body,
        note_title=note.note_title,
        folder=note.folder,
        moc=note.moc,
    )


def note_relative_path(
    item: NewsItem,
    *,
    folder: str | None = None,
    note_title: str | None = None,
) -> str:
    return build_note_relative_path(
        item_id=item.id,
        note_title=note_title or item.title,
        folder_slug=folder or "geral",
    )


def build_note_relative_path(
    *,
    item_id: int,
    note_title: str,
    folder_slug: str | None = None,
) -> str:
    display_title = humanize_filename(note_title)
    base = PurePosixPath(OBSIDIAN_FOLDER)
    if folder_slug:
        base = base / folder_display_name(folder_slug)
    return str(base / f"{item_id} - {display_title}.md")


def _encode_vault_path(relative_path: str) -> str:
    return "/".join(quote(part, safe="") for part in relative_path.replace("\\", "/").split("/"))


def _vault_file_url(relative_path: str) -> str:
    return f"{OBSIDIAN_REST_URL}/vault/{_encode_vault_path(relative_path)}"


def check_rest_connection() -> tuple[bool, str | None]:
    if not OBSIDIAN_REST_API_KEY:
        return False, "OBSIDIAN_REST_API_KEY não configurada."

    try:
        with httpx.Client(verify=OBSIDIAN_VERIFY_SSL, timeout=5.0) as client:
            response = client.get(
                f"{OBSIDIAN_REST_URL}/",
                headers={"Authorization": f"Bearer {OBSIDIAN_REST_API_KEY}"},
            )
            if response.status_code != 200:
                return False, f"Obsidian respondeu HTTP {response.status_code}."
            payload = response.json()
            if payload.get("authenticated") is True:
                return True, None
            return False, "API key rejeitada — confira em Obsidian → Settings → Local REST API."
    except httpx.ConnectError:
        return False, "Obsidian não está acessível. Abra o app e ative o plugin Local REST API."
    except Exception as exc:
        logger.exception("Obsidian REST health check failed")
        return False, str(exc)


def _write_via_rest(relative_path: str, content: str) -> None:
    headers = {
        "Authorization": f"Bearer {OBSIDIAN_REST_API_KEY}",
        "Content-Type": "text/markdown",
    }
    with httpx.Client(verify=OBSIDIAN_VERIFY_SSL, timeout=30.0) as client:
        response = client.put(_vault_file_url(relative_path), content=content, headers=headers)
        if response.status_code not in (200, 204):
            detail = response.text[:200] if response.text else response.reason_phrase
            raise RuntimeError(f"Falha ao gravar {relative_path}: HTTP {response.status_code} — {detail}")


def _open_in_obsidian(relative_path: str) -> None:
    if not OBSIDIAN_OPEN_AFTER_EXPORT:
        return

    headers = {"Authorization": f"Bearer {OBSIDIAN_REST_API_KEY}"}
    open_url = f"{OBSIDIAN_REST_URL}/open/{_encode_vault_path(relative_path)}"
    with httpx.Client(verify=OBSIDIAN_VERIFY_SSL, timeout=10.0) as client:
        response = client.post(open_url, headers=headers)
        if response.status_code not in (200, 204):
            logger.warning("Obsidian open failed for %s: %s", relative_path, response.status_code)


def _write_via_filesystem(relative_path: str, content: str) -> None:
    vault_root = Path(OBSIDIAN_VAULT_PATH)
    if not vault_root.is_dir():
        raise RuntimeError(f"OBSIDIAN_VAULT_PATH inválido: {OBSIDIAN_VAULT_PATH}")

    destination = vault_root / Path(relative_path.replace("/", os.sep))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


async def format_items_for_obsidian(
    items: list[NewsItem],
    *,
    use_agent: bool = True,
    on_progress: ObsidianProgressCallback | None = None,
) -> list[tuple[NewsItem, ObsidianNoteResult]]:
    async def format_one(item: NewsItem) -> tuple[NewsItem, ObsidianNoteResult]:
        return item, await generate_obsidian_note(
            item, use_agent=use_agent, on_progress=on_progress
        )

    if len(items) == 1:
        return [await format_one(items[0])]

    results = await asyncio.gather(*[format_one(item) for item in items])
    return list(results)


def _make_obsidian_emit(
    emit: Callable[[dict], None] | None,
    article_index: int,
    article_total: int,
) -> ObsidianProgressCallback:
    def callback(step_id: str, status: str, detail: str | None = None) -> None:
        if emit is None:
            return
        event: dict = {
            "type": "step",
            "step_id": step_id,
            "status": status,
            "article_index": article_index,
            "article_total": article_total,
        }
        if detail:
            event["detail"] = detail
        emit(event)

    return callback


async def export_items_to_obsidian(
    items: list[NewsItem],
    emit: Callable[[dict], None] | None = None,
) -> dict:
    _reload_settings()
    mode = get_obsidian_mode()
    write_mode = get_obsidian_write_mode()
    if mode is None or write_mode is None:
        raise RuntimeError(
            "Obsidian não configurado. Defina OBSIDIAN_REST_API_KEY (plugin Local REST API) "
            "ou OBSIDIAN_VAULT_PATH no .env do backend."
        )

    if write_mode == "filesystem" and not _vault_is_configured():
        raise RuntimeError(f"OBSIDIAN_VAULT_PATH inválido: {OBSIDIAN_VAULT_PATH}")

    try:
        from app.services.obsidian_vault import ensure_moc_stubs

        ensure_moc_stubs()
    except Exception as exc:
        logger.warning("Could not ensure MOC stubs: %s", exc)

    if mode == "rest":
        connected, message = check_rest_connection()
        if not connected:
            raise RuntimeError(message or "Não foi possível conectar ao Obsidian.")

    exported_paths: list[str] = []
    exported_ids: list[int] = []
    errors: list[str] = []
    total = len(items)

    for index, item in enumerate(items, start=1):
        progress = _make_obsidian_emit(emit, index, total)
        try:
            note = await generate_obsidian_note(item, use_agent=True, on_progress=progress)
            relative_path = note_relative_path(
                item,
                folder=note.folder,
                note_title=note.note_title,
            )
            markdown = build_obsidian_note(
                item,
                note.body,
                note_title=note.note_title,
                folder=note.folder,
                moc=note.moc,
            )

            if emit:
                emit(
                    {
                        "type": "step",
                        "step_id": "write",
                        "status": "active",
                        "detail": relative_path,
                        "article_index": index,
                        "article_total": total,
                    }
                )

            if write_mode == "rest":
                _write_via_rest(relative_path, markdown)
            else:
                _write_via_filesystem(relative_path, markdown)

            exported_paths.append(relative_path)
            exported_ids.append(item.id)
            if emit:
                emit(
                    {
                        "type": "step",
                        "step_id": "write",
                        "status": "done",
                        "detail": relative_path,
                        "article_index": index,
                        "article_total": total,
                    }
                )
        except Exception as exc:
            errors.append(f"{item.id}: {exc}")
            if emit:
                emit({"type": "error", "message": str(exc)})

    rest_available = False
    if mode in ("rest", "hybrid") and OBSIDIAN_REST_API_KEY:
        rest_available, _ = check_rest_connection()

    if rest_available and exported_paths and OBSIDIAN_OPEN_AFTER_EXPORT:
        try:
            _open_in_obsidian(exported_paths[0])
        except Exception as exc:
            logger.warning("Could not open note in Obsidian UI: %s", exc)

    return {
        "exported": len(exported_paths),
        "exported_ids": exported_ids,
        "paths": exported_paths,
        "mode": mode,
        "errors": errors,
    }


def mark_items_obsidian_exported(db, item_ids: list[int]) -> None:
    if not item_ids:
        return

    exported_at = datetime.now(timezone.utc)
    items = db.scalars(select(NewsItem).where(NewsItem.id.in_(item_ids))).all()
    for item in items:
        item.obsidian_exported_at = exported_at
    db.commit()
