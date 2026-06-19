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


def test_pipeline_steps_endpoint(client: TestClient):
    response = client.get("/api/pipeline/steps")
    assert response.status_code == 200, response.text
    data = response.json()
    assert "ingest" in data
    assert "backfill" in data
    ingest_ids = [step["id"] for step in data["ingest"]]
    assert ingest_ids[0] == "fetch"
    assert ingest_ids[1] == "dedup"
    assert ingest_ids[-1] == "save"
    agent_block = ingest_ids[2:-1]
    assert agent_block == ["unified"] or agent_block == ["triador", "tradutor", "hype"]
    assert all(step["estimated_seconds"] > 0 for step in data["ingest"])


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

    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["ai_relevance"] == "RELEVANTE"
    assert items[0]["is_read"] is False


def test_list_min_hype_filter(client: TestClient):
    low = {**VALID_PAYLOAD, "url": "https://example.com/low-hype", "hype_score": 2}
    high = {**VALID_PAYLOAD, "url": "https://example.com/high-hype", "hype_score": 5}
    client.post("/api/news", json=low)
    client.post("/api/news", json=high)

    response = client.get(
        "/api/news",
        params={"ai_relevance": "RELEVANTE", "min_hype": 4},
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["hype_score"] >= 4


def test_list_obsidian_exported_filter(client: TestClient, db_session):
    from datetime import datetime, timezone

    from app.models import NewsItem

    exported_id = client.post("/api/news", json=VALID_PAYLOAD).json()["id"]
    pending_payload = {
        **VALID_PAYLOAD,
        "url": "https://example.com/pending-obsidian",
    }
    pending_id = client.post("/api/news", json=pending_payload).json()["id"]

    item = db_session.get(NewsItem, exported_id)
    item.obsidian_exported_at = datetime.now(timezone.utc)
    db_session.commit()

    pending_response = client.get(
        "/api/news",
        params={"ai_relevance": "RELEVANTE", "obsidian_exported": False},
    )
    assert pending_response.status_code == 200, pending_response.text
    pending_ids = {entry["id"] for entry in pending_response.json()["items"]}
    assert pending_id in pending_ids
    assert exported_id not in pending_ids

    exported_response = client.get(
        "/api/news",
        params={"ai_relevance": "RELEVANTE", "obsidian_exported": True},
    )
    assert exported_response.status_code == 200, exported_response.text
    exported_ids = {entry["id"] for entry in exported_response.json()["items"]}
    assert exported_id in exported_ids
    assert pending_id not in exported_ids


def test_list_bookmarked_filter(client: TestClient):
    create_response = client.post("/api/news", json=VALID_PAYLOAD)
    item_id = create_response.json()["id"]
    client.patch(f"/api/news/{item_id}/bookmark", json={"is_bookmarked": True})

    response = client.get(
        "/api/news",
        params={"is_bookmarked": True, "ai_relevance": "RELEVANTE"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["is_bookmarked"] is True


def test_patch_read_and_bookmark(client: TestClient):
    client.post("/api/news", json=VALID_PAYLOAD)
    list_response = client.get("/api/news", params={"ai_relevance": "RELEVANTE"})
    item_id = list_response.json()["items"][0]["id"]

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


def test_bulk_update_and_delete(client: TestClient):
    first = client.post("/api/news", json=VALID_PAYLOAD).json()["id"]
    second_payload = {**VALID_PAYLOAD, "url": "https://example.com/second-item"}
    second = client.post("/api/news", json=second_payload).json()["id"]

    bulk_read = client.patch(
        "/api/news/bulk",
        json={"ids": [first, second], "is_read": True},
    )
    assert bulk_read.status_code == 200
    assert bulk_read.json()["affected"] == 2

    bulk_bookmark = client.patch(
        "/api/news/bulk",
        json={"ids": [first], "is_bookmarked": True},
    )
    assert bulk_bookmark.status_code == 200
    assert bulk_bookmark.json()["affected"] == 1

    bulk_delete = client.request(
        "DELETE",
        "/api/news/bulk",
        json={"ids": [first, second]},
    )
    assert bulk_delete.status_code == 200
    assert bulk_delete.json()["affected"] == 2


def test_delete_news_item(client: TestClient):
    create_response = client.post("/api/news", json=VALID_PAYLOAD)
    item_id = create_response.json()["id"]

    delete_response = client.delete(f"/api/news/{item_id}")
    assert delete_response.status_code == 200
    assert delete_response.json()["affected"] == 1


def test_folders_and_assign(client: TestClient):
    folder_response = client.post("/api/folders", json={"name": "Inteligência Artificial"})
    assert folder_response.status_code == 201
    folder_id = folder_response.json()["id"]

    create_response = client.post("/api/news", json=VALID_PAYLOAD)
    item_id = create_response.json()["id"]

    assign_response = client.patch(
        f"/api/news/{item_id}/folder",
        json={"folder_id": folder_id},
    )
    assert assign_response.status_code == 200
    body = assign_response.json()
    assert body["folder_id"] == folder_id
    assert body["is_bookmarked"] is True

    filtered = client.get(
        "/api/news",
        params={"folder_id": folder_id, "is_bookmarked": True},
    )
    assert len(filtered.json()["items"]) == 1


def test_news_pagination_and_filters(client: TestClient):
    for index in range(3):
        client.post(
            "/api/news",
            json={
                **VALID_PAYLOAD,
                "url": f"https://example.com/page-{index}",
                "title": f"Python tutorial {index}",
                "hype_score": index + 1,
                "source": "dev.to" if index % 2 == 0 else "reddit",
            },
        )

    page_one = client.get(
        "/api/news",
        params={"ai_relevance": "RELEVANTE", "limit": 2, "offset": 0},
    )
    assert page_one.status_code == 200
    body = page_one.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0

    filtered = client.get(
        "/api/news",
        params={"ai_relevance": "RELEVANTE", "hype": 2},
    )
    assert filtered.status_code == 200
    filtered_items = filtered.json()["items"]
    assert len(filtered_items) == 1
    assert filtered_items[0]["hype_score"] == 2

    by_source = client.get(
        "/api/news",
        params={"ai_relevance": "RELEVANTE", "source": "dev.to"},
    )
    assert by_source.status_code == 200
    assert all(item["source"] == "dev.to" for item in by_source.json()["items"])

    search = client.get(
        "/api/news",
        params={"ai_relevance": "RELEVANTE", "q": "python"},
    )
    assert search.status_code == 200
    assert len(search.json()["items"]) == 3

    count = client.get(
        "/api/news/count",
        params={"ai_relevance": "RELEVANTE", "is_read": False},
    )
    assert count.status_code == 200
    assert count.json()["count"] >= 3


def test_settings_endpoints(client: TestClient):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert "background_ingest_enabled" in data
    assert "sources" in data

    # Update settings
    payload = {
        "background_ingest_enabled": True,
        "sources": {
            "dev_to": False,
            "reddit": True,
            "github_trends": True,
            "hacker_news": False,
            "rss_feeds": True
        }
    }
    update_response = client.post("/api/settings", json=payload)
    assert update_response.status_code == 200
    new_data = update_response.json()
    assert new_data["background_ingest_enabled"] is True
    assert new_data["sources"]["dev_to"] is False
    assert new_data["sources"]["reddit"] is True


def test_obsidian_concepts_endpoint(client: TestClient, db_session):
    from datetime import datetime, timezone
    
    create_response = client.post("/api/news", json=VALID_PAYLOAD)
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]
    
    from app.models import NewsItem
    item = db_session.get(NewsItem, item_id)
    item.title = "Aprenda Next.js, FastAPI e Docker"
    item.title_original = "Learn Next.js, FastAPI and Docker"
    item.description = "Tutorial cobrindo Next.js, FastAPI e Docker."
    item.obsidian_exported_at = datetime.now(timezone.utc)
    db_session.commit()
    
    response = client.get("/api/obsidian/concepts")
    assert response.status_code == 200
    concepts = response.json()
    assert len(concepts) > 0
    
    names = [c["concept"] for c in concepts]
    assert "Next.js" in names
    assert "FastAPI" in names
    assert "Docker" in names


