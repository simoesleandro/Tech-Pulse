import app.services.settings as settings_module
from app.services.settings import load_settings, save_settings


def test_load_settings_is_cached(monkeypatch, tmp_path):
    """Second call must not read from disk."""
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "s.json")
    monkeypatch.setattr(settings_module, "_settings_cache", None)

    read_count = [0]
    real_open = open

    def counting_open(path, *a, **kw):
        fh = real_open(path, *a, **kw)
        if str(path) == str(tmp_path / "s.json") and "r" in a:
            read_count[0] += 1
        return fh

    monkeypatch.setattr("builtins.open", counting_open)
    load_settings()
    after_first = read_count[0]
    load_settings()
    assert read_count[0] == after_first, "load_settings read disk on second call"


def test_save_settings_invalidates_cache(monkeypatch, tmp_path):
    """save_settings must set _settings_cache to None."""
    monkeypatch.setattr(settings_module, "SETTINGS_FILE", tmp_path / "s.json")
    monkeypatch.setattr(settings_module, "_settings_cache", None)

    load_settings()
    assert settings_module._settings_cache is not None
    save_settings(settings_module._settings_cache or {})
    assert settings_module._settings_cache is None
