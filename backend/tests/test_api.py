from fastapi.testclient import TestClient

VALID_PAYLOAD = {
    "title": "Construindo um orquestrador de agentes LLM com Python",
    "title_original": "Building an LLM Agent Orchestrator from Scratch with Python",
    "description": "Artigo sobre orquestração de agentes com Python.",
    "url": "https://example.com/llm-agent",
    "source": "dev.to",
    "ai_relevance": "RELEVANTE",
    "hype_score": 4,
}

JUNK_PAYLOAD = {
    "title": "CEO captura US$ 50M em Série A",
    "title_original": "CEO raises 50M in Series A",
    "description": "Notícia corporativa.",
    "url": "https://example.com/ceo-funding",
    "source": "reddit",
    "ai_relevance": "LIXO",
    "hype_score": 1,
}


def test_health_check(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "techpulse-api"}


def test_create_valid_news(client: TestClient):
    response = client.post("/api/news", json=VALID_PAYLOAD)
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["title"] == VALID_PAYLOAD["title"]
    assert data["url"] == VALID_PAYLOAD["url"]
    assert data["is_read"] is False
    assert data["is_bookmarked"] is False
    assert "id" in data
    assert "created_at" in data


def test_duplicate_url_returns_400(client: TestClient):
    client.post("/api/news", json=VALID_PAYLOAD)
    response = client.post("/api/news", json=VALID_PAYLOAD)
    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "URL já cadastrada"


def test_list_filtered_news(client: TestClient):
    client.post("/api/news", json=VALID_PAYLOAD)
    client.post("/api/news", json=JUNK_PAYLOAD)

    response = client.get(
        "/api/news", params={"ai_relevance": "RELEVANTE", "is_read": False}
    )
    assert response.status_code == 200, response.text

    items = response.json()
    assert len(items) == 1
    assert items[0]["ai_relevance"] == "RELEVANTE"
    assert items[0]["is_read"] is False


def test_list_bookmarked_filter(client: TestClient):
    create_response = client.post("/api/news", json=VALID_PAYLOAD)
    item_id = create_response.json()["id"]
    client.patch(f"/api/news/{item_id}/bookmark", json={"is_bookmarked": True})

    response = client.get(
        "/api/news",
        params={"is_bookmarked": True, "ai_relevance": "RELEVANTE"},
    )
    assert response.status_code == 200
    items = response.json()
    assert len(items) == 1
    assert items[0]["is_bookmarked"] is True


def test_patch_read_and_bookmark(client: TestClient):
    client.post("/api/news", json=VALID_PAYLOAD)
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


def test_seed_demo_articles(client: TestClient):
    response = client.post("/api/seed")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["created"] == 4
    assert body["skipped"] == 0

    second = client.post("/api/seed")
    assert second.json()["created"] == 0
    assert second.json()["skipped"] == 4


def test_patch_not_found_returns_404(client: TestClient):
    response = client.patch("/api/news/9999/read", json={"is_read": True})
    assert response.status_code == 404
    assert response.json()["detail"] == "Notícia não encontrada"
