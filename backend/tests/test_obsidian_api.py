from unittest.mock import AsyncMock, patch


def test_obsidian_status_unconfigured(client, monkeypatch):
    monkeypatch.setattr("app.services.obsidian.get_obsidian_mode", lambda: None)

    response = client.get("/api/obsidian/status")
    assert response.status_code == 200
    body = response.json()
    assert body["configured"] is False
    assert "OBSIDIAN" in body["message"]


def test_obsidian_status_hybrid_vault_ok_rest_offline(client, monkeypatch):
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp_dir:
        monkeypatch.setattr("app.services.obsidian._reload_settings", lambda: None)
        monkeypatch.setattr("app.services.obsidian.OBSIDIAN_REST_API_KEY", "test-key")
        monkeypatch.setattr("app.services.obsidian.OBSIDIAN_VAULT_PATH", tmp_dir)
        monkeypatch.setattr(
            "app.main.check_rest_connection",
            lambda: (False, "REST offline"),
        )

        response = client.get("/api/obsidian/status")
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "hybrid"
        assert body["connected"] is True
        assert "REST offline" in body["message"]


def test_obsidian_format_endpoint(client):
    create = client.post(
        "/api/news",
        json={
            "title": "Nota formatada",
            "title_original": "Formatted note",
            "description": "Conteúdo sobre Rust.",
            "url": "https://example.com/rust-note",
            "source": "dev.to",
            "ai_relevance": "RELEVANTE",
            "hype_score": 3,
        },
    )
    item_id = create.json()["id"]

    with patch(
        "app.services.obsidian.generate_obsidian_body",
        new=AsyncMock(
            return_value="# Nota formatada\n\n> [!abstract] O que é\n> Rust é uma linguagem de sistemas.\n\n## Desenvolvimento\n\n### Memória\n- Ownership"
        ),
    ):
        response = client.post("/api/obsidian/format", json={"ids": [item_id]})

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["id"] == item_id
    assert "> [!abstract] O que é" in body["markdown"]
    assert "techpulse_id" in body["markdown"]


def test_obsidian_export_requires_config(client, monkeypatch):
    monkeypatch.setattr("app.services.obsidian.get_obsidian_mode", lambda: None)

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
