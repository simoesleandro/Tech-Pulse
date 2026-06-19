import json
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
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        merged = _merge_with_defaults(raw if isinstance(raw, dict) else {})
        return AppSettings.model_validate(merged).model_dump()
    except Exception:
        return AppSettings.model_validate(DEFAULT_SETTINGS).model_dump()


def save_settings(settings: dict) -> None:
    validated = AppSettings.model_validate(_merge_with_defaults(settings)).model_dump()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(validated, f, indent=2, ensure_ascii=False)
