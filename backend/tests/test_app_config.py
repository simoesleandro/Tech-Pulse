from fastapi.testclient import TestClient

from app.config import AppConfig, get_app_config


def test_app_config_from_env(monkeypatch):
    get_app_config.cache_clear()
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test,http://b.test")
    monkeypatch.setenv("ALLOW_SEED", "false")
    monkeypatch.setenv("INGEST_BATCH_SIZE", "10")

    config = AppConfig.from_env()
    assert config.cors_origins == ["http://a.test", "http://b.test"]
    assert config.allow_seed is False
    assert config.ingest_batch_size == 10

    get_app_config.cache_clear()


def test_app_config_invalid_batch_size_raises():
    import os
    from unittest.mock import patch

    from pydantic import ValidationError

    env = os.environ.copy()
    env["INGEST_BATCH_SIZE"] = "0"
    with patch.dict(os.environ, env, clear=True):
        try:
            AppConfig.from_env()
            raised = False
        except ValidationError:
            raised = True
    assert raised
