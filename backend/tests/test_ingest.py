from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.services.ingest import run_ingest
from app.services.scrapers.base import EnrichedArticle, RawArticle


def _mock_fetch_devto() -> list[RawArticle]:
    return [
        RawArticle(
            title="Building an LLM Agent Orchestrator from Scratch with Python",
            url="https://dev.to/example/llm-agent",
            source="dev.to",
            description_snippet="A deep dive into agents",
            positive_reactions=20,
            comments_count=5,
        ),
        RawArticle(
            title="CEO raises 50M in Series A",
            url="https://dev.to/example/ceo-funding",
            source="dev.to",
        ),
    ]


def _mock_fetch_reddit() -> list[RawArticle]:
    return [
        RawArticle(
            title="Duplicate Article",
            url="https://dev.to/example/llm-agent",
            source="reddit",
        )
    ]


def _mock_fetch_github() -> list[RawArticle]:
    return []


def _mock_enrich(article: RawArticle) -> EnrichedArticle:
    if "LLM" in article.title or "Python" in article.title:
        return EnrichedArticle(
            ai_relevance="RELEVANTE",
            title_pt="Construindo um orquestrador de agentes LLM com Python",
            description_pt="Artigo sobre orquestração de agentes de IA com Python.",
        )
    return EnrichedArticle(
        ai_relevance="LIXO",
        title_pt="CEO captura US$ 50M em Série A",
        description_pt="Notícia corporativa sem foco técnico.",
    )


def test_ingest_pipeline(db_session: Session):
    db_session.add(
        NewsItem(
            title="Existente",
            title_original="Existing",
            description="Já existia",
            url="https://dev.to/example/llm-agent",
            source="dev.to",
            ai_relevance="RELEVANTE",
            hype_score=3,
        )
    )
    db_session.commit()

    stats = run_ingest(
        db_session,
        fetchers=[_mock_fetch_devto, _mock_fetch_reddit, _mock_fetch_github],
        enricher=_mock_enrich,
    )

    assert stats["fetched"] == 3
    assert stats["skipped_duplicate"] == 2
    assert stats["classified"] == 1
    assert stats["saved"] == 1
    assert stats["relevante"] == 0
    assert stats["lixo"] == 1

    saved = db_session.scalars(
        select(NewsItem).where(NewsItem.url == "https://dev.to/example/ceo-funding")
    ).one()
    assert saved.title.startswith("CEO")
    assert saved.description
    assert saved.hype_score >= 0


def test_ingest_endpoint(client: TestClient):
    mock_stats = {
        "fetched": 2,
        "skipped_duplicate": 0,
        "classified": 2,
        "saved": 2,
        "relevante": 1,
        "lixo": 1,
        "errors": [],
    }

    with patch("app.main.run_ingest", return_value=mock_stats):
        response = client.post("/api/ingest")

    assert response.status_code == 200, response.text
    assert response.json() == mock_stats
