def test_obsidian_status_unconfigured(client):
    response = client.get("/api/obsidian/status")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert "OBSIDIAN" in body["message"]


def test_obsidian_export_requires_config(client):
    create = client.post(
        "/api/news",
        json={
            "title": "Nota Obsidian",
            "title_original": "Obsidian note",
            "description": "Teste.",
            "url": "https://example.com/obsidian-test",
            "source": "dev.to",
            "ai_relevance": "RELEVANTE",
            "hype_score": 3,
        },
    )
    item_id = create.json()["id"]

    response = client.post("/api/obsidian/export", json={"ids": [item_id]})
    assert response.status_code == 503
