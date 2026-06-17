import datetime
from unittest.mock import MagicMock, patch
from datetime import timezone
from app.models import NewsItem, TopicFolder
from app.services.obsidian_digest import generate_weekly_digest

def test_generate_weekly_digest(db_session):
    # 1. Setup Mock Config
    mock_config = {
        "configured": True,
        "mode": "filesystem",
        "folder": "Tech-Pulse",
        "connected": True,
        "message": "Vault ok"
    }

    # 2. Setup Test Data (TopicFolder & NewsItems)
    folder_ia = TopicFolder(name="🤖 IA")
    folder_devops = TopicFolder(name="DevOps")
    db_session.add(folder_ia)
    db_session.add(folder_devops)
    db_session.commit()

    now = datetime.datetime.now(timezone.utc)
    old = now - datetime.timedelta(days=10)

    # 5 items within 7 days, 1 item older
    item1 = NewsItem(
        title="Matéria IA",
        title_original="AI Stuff",
        description="Forte avanço de IA.",
        url="https://example.com/ai",
        source="dev.to",
        ai_relevance="RELEVANTE",
        hype_score=5,
        ai_reasoning="Novidade 5 · Utilidade 5 — Muito bom.",
        folder_id=folder_ia.id,
        obsidian_exported_at=now,
        created_at=now,
    )
    item2 = NewsItem(
        title="Matéria DevOps",
        title_original="DevOps Stuff",
        description="Kubernetes 1.30.",
        url="https://example.com/devops",
        source="reddit",
        ai_relevance="RELEVANTE",
        hype_score=4,
        ai_reasoning="Novidade 4 · Utilidade 4 — Recomendo.",
        folder_id=folder_devops.id,
        obsidian_exported_at=None,
        created_at=now,
    )
    item3 = NewsItem(
        title="Antigo",
        title_original="Old",
        description="Muito velho.",
        url="https://example.com/old",
        source="dev.to",
        ai_relevance="RELEVANTE",
        hype_score=5,
        created_at=old,
    )
    item4 = NewsItem(
        title="Lixo Semana",
        title_original="Spam",
        description="Propaganda.",
        url="https://example.com/spam",
        source="dev.to",
        ai_relevance="LIXO",
        hype_score=3,
        created_at=now,
    )

    db_session.add(item1)
    db_session.add(item2)
    db_session.add(item3)
    db_session.add(item4)
    db_session.commit()

    # 3. Call generate_weekly_digest and Mock write_file_to_obsidian
    with patch("app.services.obsidian_digest.get_obsidian_config", return_value=mock_config), \
         patch("app.services.obsidian_digest.write_file_to_obsidian") as mock_write:
        
        path = generate_weekly_digest(db_session)
        
        # Assert path format
        assert path.startswith("📚 Índices/Digest-")
        assert path.endswith(".md")

        # Assert write was called
        mock_write.assert_called_once()
        written_path, written_content = mock_write.call_args[0]
        assert written_path == path

        # Assert content contains expected elements
        assert "# Tech-Pulse — Digest Semanal" in written_content
        assert "🏆 Top 5 Hype da Semana" in written_content
        assert "📚 Artigos da Semana por Área" in written_content
        
        # Check that top items are present
        assert "Matéria IA" in written_content
        assert "Matéria DevOps" in written_content
        
        # Check that old item is NOT present
        assert "Antigo" not in written_content
        
        # Check that spam is NOT present
        assert "Lixo Semana" not in written_content

        # Check grouping
        assert "### 🤖 IA" in written_content
        assert "### DevOps" in written_content

        # Check wikilink for exported item and normal link for unexported
        note_name = f"{item1.id} - Matéria IA" # humanized
        assert f"[[{note_name}|Matéria IA]]" in written_content
        assert f"[Matéria DevOps](https://example.com/devops)" in written_content
