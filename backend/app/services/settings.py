import json
import threading
from pathlib import Path

from app.schemas import AppSettings

SETTINGS_FILE = Path(__file__).resolve().parents[2] / "settings.json"

DEFAULT_SETTINGS: dict = AppSettings(
    background_ingest_enabled=False,
    obsidian_auto_export=False,
    pipeline_mode="unified",
    sources={
        "dev_to": True,
        "reddit": True,
        "github_trends": True,
        "hacker_news": True,
        "rss_feeds": True,
    },
).model_dump()

_settings_lock = threading.Lock()
_settings_cache: dict | None = None


def _merge_with_defaults(data: dict) -> dict:
    merged = {**DEFAULT_SETTINGS, **data}
    default_sources = DEFAULT_SETTINGS["sources"]
    sources = merged.get("sources")
    if isinstance(sources, dict):
        merged["sources"] = {**default_sources, **sources}
    else:
        merged["sources"] = default_sources
    return merged


def load_settings() -> dict:
    global _settings_cache
    with _settings_lock:
        if _settings_cache is not None:
            return dict(_settings_cache)
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        result = DEFAULT_SETTINGS.copy()
        with _settings_lock:
            _settings_cache = result
        return dict(result)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        merged = _merge_with_defaults(raw if isinstance(raw, dict) else {})
        result = AppSettings.model_validate(merged).model_dump()
    except Exception:
        result = AppSettings.model_validate(DEFAULT_SETTINGS).model_dump()
    with _settings_lock:
        _settings_cache = result
    return dict(result)


def save_settings(settings: dict) -> None:
    global _settings_cache
    validated = AppSettings.model_validate(_merge_with_defaults(settings)).model_dump()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(validated, f, indent=2, ensure_ascii=False)
    with _settings_lock:
        _settings_cache = None
