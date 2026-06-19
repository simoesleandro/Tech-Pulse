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
            hype_score=4,
        )
    return EnrichedArticle(
        ai_relevance="LIXO",
        title_pt="CEO captura US$ 50M em Série A",
        description_pt="Notícia corporativa sem foco técnico.",
        hype_score=1,
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


def test_ingest_skips_url_variants_as_duplicates(db_session: Session):
    db_session.add(
        NewsItem(
            title="Artigo existente",
            title_original="Existing article",
            description="Já no feed",
            url="https://Example.com/article",
            source="rss/test",
            ai_relevance="RELEVANTE",
            hype_score=4,
        )
    )
    db_session.commit()

    def fetch_variant() -> list[RawArticle]:
        return [
            RawArticle(
                title="Same article",
                url="https://www.example.com/article/",
                source="rss/test",
            )
        ]

    stats = run_ingest(
        db_session,
        fetchers=[fetch_variant],
        enricher=_mock_enrich,
    )

    assert stats["fetched"] == 1
    assert stats["skipped_duplicate"] == 1
    assert stats["saved"] == 0


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


def test_ingest_stream_endpoint(client: TestClient):
    mock_stats = {
        "fetched": 1,
        "skipped_duplicate": 0,
        "classified": 1,
        "saved": 1,
        "relevante": 1,
        "lixo": 0,
        "errors": [],
    }
    events: list[dict] = []

    def fake_ingest(db, on_progress=None, **kwargs):
        if on_progress:
            on_progress(
                {
                    "type": "step",
                    "step_id": "fetch",
                    "status": "done",
                    "detail": "1 artigo",
                }
            )
        return mock_stats

    with patch("app.main.run_ingest", side_effect=fake_ingest):
        response = client.post("/api/ingest/stream")

    assert response.status_code == 200, response.text
    assert "text/event-stream" in response.headers.get("content-type", "")

    for line in response.text.strip().split("\n\n"):
        if line.startswith("data: "):
            import json

            events.append(json.loads(line[6:]))

    assert any(event.get("step_id") == "fetch" for event in events)
    assert events[-1]["type"] == "complete"
    assert events[-1]["result"] == mock_stats


def test_ingest_emits_progress_events(db_session: Session):
    events: list[dict] = []

    def on_progress(event: dict) -> None:
        events.append(event)

    stats = run_ingest(
        db_session,
        fetchers=[_mock_fetch_devto, _mock_fetch_github],
        enricher=_mock_enrich,
        on_progress=on_progress,
    )

    assert stats["saved"] == 2
    step_ids = [event["step_id"] for event in events if event.get("type") == "step"]
    assert "fetch" in step_ids
    assert "dedup" in step_ids
    assert "save" in step_ids
