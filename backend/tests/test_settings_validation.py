from app.services.settings import _merge_with_defaults, load_settings, save_settings
from app.schemas import AppSettings


def test_merge_with_defaults_fills_missing_sources():
    merged = _merge_with_defaults({"background_ingest_enabled": True})
    validated = AppSettings.model_validate(merged)
    assert validated.sources.dev_to is True
    assert validated.background_ingest_enabled is True


def test_save_settings_rejects_invalid_pipeline_mode(tmp_path, monkeypatch):
    from app.services import settings as settings_module

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", settings_file)

    save_settings({"pipeline_mode": "unified"})
    loaded = load_settings()
    assert loaded["pipeline_mode"] == "unified"

    save_settings({"pipeline_mode": "unified", "obsidian_auto_export": True})
    loaded = load_settings()
    assert loaded["obsidian_auto_export"] is True
