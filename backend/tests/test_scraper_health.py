"""Testes para o source health monitor."""
import pytest
from datetime import datetime, timezone

from app.models import ScraperRun
from app.schemas import ScraperHealthResponse, SystemHealthResponse


def test_scraper_run_model_creation():
    """ScraperRun pode ser instanciado com os campos esperados."""
    run = ScraperRun(
        source="dev.to",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        items_found=42,
        error=None,
    )
    assert run.source == "dev.to"
    assert run.items_found == 42
    assert run.error is None


def test_scraper_health_response_schema():
    response = ScraperHealthResponse(
        source="Reddit",
        last_run_at=datetime.now(timezone.utc),
        last_success_at=datetime.now(timezone.utc),
        last_items_found=10,
        last_error=None,
        status="ok",
    )
    assert response.status == "ok"


def test_scraper_health_error_status():
    response = ScraperHealthResponse(
        source="GitHub Trends",
        last_run_at=datetime.now(timezone.utc),
        last_success_at=None,
        last_items_found=0,
        last_error="Connection timeout",
        status="error",
    )
    assert response.status == "error"
    assert response.last_error == "Connection timeout"


def test_scraper_health_never_run():
    response = ScraperHealthResponse(
        source="Hacker News",
        last_run_at=None,
        last_success_at=None,
        last_items_found=0,
        last_error=None,
        status="never_run",
    )
    assert response.status == "never_run"
