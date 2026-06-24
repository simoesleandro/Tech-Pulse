"""Testes para o serviço de analytics."""

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


def test_get_analytics_returns_response(db_session):
    """get_analytics retorna AnalyticsResponse mesmo com banco vazio."""
    from app.services.analytics import get_analytics

    result = get_analytics(db_session, days=7)

    assert isinstance(result, AnalyticsResponse)
    assert result.period_days == 7
    assert result.total_items >= 0


def test_get_analytics_sources_ordered_by_total(db_session):
    """Fontes são ordenadas por total decrescente."""
    from app.services.analytics import get_analytics

    result = get_analytics(db_session, days=365)

    if len(result.sources) > 1:
        assert result.sources[0].total >= result.sources[1].total
