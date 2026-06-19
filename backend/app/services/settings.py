import json
from pathlib import Path

SETTINGS_FILE = Path(__file__).resolve().parents[2] / "settings.json"

DEFAULT_SETTINGS = {
    "background_ingest_enabled": False,
    "obsidian_auto_export": False,
    "pipeline_mode": "unified",
    "sources": {
        "dev_to": True,
        "reddit": True,
        "github_trends": True,
        "hacker_news": True,
        "rss_feeds": True
    }
}

def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Guarantee all fields exist (fallback to default)
            for k, v in DEFAULT_SETTINGS.items():
                if k not in data:
                    data[k] = v
            # Ensure sources dict is complete
            if isinstance(data.get("sources"), dict):
                for sk, sv in DEFAULT_SETTINGS["sources"].items():
                    if sk not in data["sources"]:
                        data["sources"][sk] = sv
            else:
                data["sources"] = DEFAULT_SETTINGS["sources"]
            return data
    except Exception:
        return DEFAULT_SETTINGS

def save_settings(settings: dict) -> None:
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
