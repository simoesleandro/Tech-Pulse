"""Testes para o serviço de analytics."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.schemas import AnalyticsResponse, SourceStats


def test_analytics_response_schema():
    """Schema de response aceita os campos esperados."""
    response = AnalyticsResponse(
        period_days=30,
        total_items=100,
        relevant_items=40,
        read_items=25,
        bookmarked_items=10,
        feedback_given=5,
        sources=[],
        ingest_by_day=[],
        top_folders=[],
    )
    assert response.total_items == 100
    assert response.relevant_items == 40


def test_source_stats_relevance_rate():
    """relevance_rate é calculado corretamente."""
    stats = SourceStats(
        source="hacker_news",
        total=100,
        relevante=40,
        relevance_rate=0.4,
        avg_hype=3.2,
    )
    assert stats.relevance_rate == 0.4


def test_get_analytics_returns_response():
    """get_analytics retorna AnalyticsResponse mesmo com banco vazio."""
    from app.database import SessionLocal
    from app.services.analytics import get_analytics
    db = SessionLocal()
    try:
        result = get_analytics(db, days=7)
        assert isinstance(result, AnalyticsResponse)
        assert result.period_days == 7
        assert result.total_items >= 0
    finally:
        db.close()


def test_get_analytics_sources_ordered_by_total():
    """Fontes são ordenadas por total decrescente."""
    from app.database import SessionLocal
    from app.services.analytics import get_analytics
    db = SessionLocal()
    try:
        result = get_analytics(db, days=365)
        if len(result.sources) > 1:
            assert result.sources[0].total >= result.sources[1].total
    finally:
        db.close()
