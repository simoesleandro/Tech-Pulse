from collections.abc import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.models import NewsItem
from app.services.ingest import run_ingest
from app.services.scrapers.base import RawArticle

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def _mock_fetch_devto() -> list[RawArticle]:
    return [
        RawArticle(
            title="Building an LLM Agent Orchestrator from Scratch with Python",
            url="https://dev.to/example/llm-agent",
            source="dev.to",
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


def _mock_classifier(title: str) -> str:
    if "LLM" in title or "Python" in title:
        return "RELEVANTE"
    return "LIXO"


def _get_test_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_ingest_pipeline():
    Base.metadata.create_all(bind=test_engine)
    db = TestSessionLocal()

    try:
        db.add(
            NewsItem(
                title="Existing",
                url="https://dev.to/example/llm-agent",
                source="dev.to",
                ai_relevance="RELEVANTE",
            )
        )
        db.commit()

        stats = run_ingest(
            db,
            fetchers=[_mock_fetch_devto, _mock_fetch_reddit, _mock_fetch_github],
            classifier=_mock_classifier,
        )

        assert stats["fetched"] == 3
        assert stats["skipped_duplicate"] == 2
        assert stats["classified"] == 1
        assert stats["saved"] == 1
        assert stats["relevante"] == 0
        assert stats["lixo"] == 1
        assert len(stats["errors"]) == 0

        items = db.scalars(select(NewsItem).order_by(NewsItem.id)).all()
        assert len(items) == 2
        assert items[-1].ai_relevance == "LIXO"
        assert items[-1].url == "https://dev.to/example/ceo-funding"
    finally:
        db.close()


def test_ingest_endpoint():
    from unittest.mock import patch

    from fastapi.testclient import TestClient

    from app.main import app

    mock_stats = {
        "fetched": 2,
        "skipped_duplicate": 0,
        "classified": 2,
        "saved": 2,
        "relevante": 1,
        "lixo": 1,
        "errors": [],
    }

    app.dependency_overrides[get_db] = _get_test_db

    with patch("app.main.run_ingest", return_value=mock_stats):
        with TestClient(app) as client:
            response = client.post("/api/ingest")

    app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    assert response.json() == mock_stats


if __name__ == "__main__":
    test_ingest_pipeline()
    print("test_ingest_pipeline: OK")

    test_ingest_endpoint()
    print("test_ingest_endpoint: OK")
    print("Todos os testes de ingestão passaram.")