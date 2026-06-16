import logging
import os
import re
import unicodedata
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx
from dotenv import load_dotenv

from app.models import NewsItem

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
    if OBSIDIAN_REST_API_KEY:
        return "rest"
    if OBSIDIAN_VAULT_PATH:
        return "filesystem"
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
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", ascii_text.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:max_len] or "nota"


def _escape_yaml(value: str) -> str:
    return value.replace('"', '\\"')


def news_item_to_markdown(item: NewsItem) -> str:
    source_tag = item.source.replace("/", "-").replace(".", "-")
    tags = ["tech-pulse", source_tag]
    reasoning = (item.ai_reasoning or "").strip()

    return f"""---
title: "{_escape_yaml(item.title)}"
source: {item.source}
url: {item.url}
hype: {item.hype_score}
tags: [{", ".join(tags)}]
techpulse_id: {item.id}
created: {item.created_at.isoformat()}
---

# {item.title}

{item.description.strip()}

{f"> **Análise de hype:** {reasoning}" if reasoning else ""}

[Abrir original]({item.url})
"""


def note_relative_path(item: NewsItem) -> str:
    slug = slugify_title(item.title)
    return str(PurePosixPath(OBSIDIAN_FOLDER) / f"{item.id}-{slug}.md")


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


def export_items_to_obsidian(items: list[NewsItem]) -> dict:
    _reload_settings()
    mode = get_obsidian_mode()
    if mode is None:        raise RuntimeError(
            "Obsidian não configurado. Defina OBSIDIAN_REST_API_KEY (plugin Local REST API) "
            "ou OBSIDIAN_VAULT_PATH no .env do backend."
        )

    if mode == "rest":
        connected, message = check_rest_connection()
        if not connected:
            raise RuntimeError(message or "Não foi possível conectar ao Obsidian.")

    exported_paths: list[str] = []
    errors: list[str] = []

    for item in items:
        relative_path = note_relative_path(item)
        markdown = news_item_to_markdown(item)
        try:
            if mode == "rest":
                _write_via_rest(relative_path, markdown)
            else:
                _write_via_filesystem(relative_path, markdown)
            exported_paths.append(relative_path)
        except Exception as exc:
            errors.append(f"{item.id}: {exc}")

    if mode == "rest" and exported_paths and OBSIDIAN_OPEN_AFTER_EXPORT:
        try:
            _open_in_obsidian(exported_paths[0])
        except Exception as exc:
            logger.warning("Could not open note in Obsidian UI: %s", exc)

    return {
        "exported": len(exported_paths),
        "paths": exported_paths,
        "mode": mode,
        "errors": errors,
    }
