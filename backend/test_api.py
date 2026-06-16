from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"

test_engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db() -> Generator[Session, None, None]:
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
Base.metadata.create_all(bind=test_engine)

client = TestClient(app)

VALID_PAYLOAD = {
    "title": "Building an LLM Agent Orchestrator from Scratch with Python",
    "url": "https://example.com/llm-agent",
    "source": "dev.to",
    "ai_relevance": "RELEVANTE",
}

JUNK_PAYLOAD = {
    "title": "CEO raises 50M in Series A",
    "url": "https://example.com/ceo-funding",
    "source": "reddit",
    "ai_relevance": "LIXO",
}


def test_create_valid_news():
    response = client.post("/api/news", json=VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"] == VALID_PAYLOAD["title"]
    assert data["url"] == VALID_PAYLOAD["url"]
    assert data["is_read"] is False
    assert data["is_bookmarked"] is False
    assert "id" in data
    assert "created_at" in data


def test_duplicate_url_returns_400():
    response = client.post("/api/news", json=VALID_PAYLOAD)
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "URL já cadastrada"


def test_list_filtered_news():
    client.post("/api/news", json=JUNK_PAYLOAD)

    response = client.get("/api/news", params={"ai_relevance": "RELEVANTE", "is_read": False})
    assert response.status_code == 200, response.text

    items = response.json()
    assert len(items) == 1
    assert items[0]["ai_relevance"] == "RELEVANTE"
    assert items[0]["is_read"] is False


def test_patch_read_and_bookmark():
    list_response = client.get("/api/news", params={"ai_relevance": "RELEVANTE"})
    item_id = list_response.json()[0]["id"]

    read_response = client.patch(f"/api/news/{item_id}/read", json={"is_read": True})
    assert read_response.status_code == 200, read_response.text
    assert read_response.json()["is_read"] is True

    bookmark_response = client.patch(
        f"/api/news/{item_id}/bookmark", json={"is_bookmarked": True}
    )
    assert bookmark_response.status_code == 200, bookmark_response.text
    assert bookmark_response.json()["is_bookmarked"] is True


if __name__ == "__main__":
    test_create_valid_news()
    test_duplicate_url_returns_400()
    test_list_filtered_news()
    test_patch_read_and_bookmark()
    print("Todos os testes passaram.")
