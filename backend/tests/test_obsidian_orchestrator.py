from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from app.models import NewsItem
from app.services.obsidian_orchestrator import (
    agente_orquestrador_obsidian,
    fallback_orchestration,
    merge_orchestration,
)


def _sample_item(**overrides) -> NewsItem:
    defaults = {
        "id": 1,
        "title": "Building LLM agents with Python",
        "title_original": "Building LLM agents with Python",
        "description": "Guia sobre agentes.",
        "url": "https://example.com/agents",
        "source": "dev.to",
        "ai_relevance": "RELEVANTE",
        "hype_score": 4,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(overrides)
    return NewsItem(**defaults)


def test_fallback_orchestration_picks_ia_folder():
    analysis = {
        "tema": "Orquestração de agentes LLM com Ollama",
        "termos": [{"termo": "Agente", "definicao": "Loop com tools"}],
        "wikilinks": ["Python"],
    }
    result = fallback_orchestration(_sample_item(), analysis)
    assert result["pasta"] == "ia-llms"
    assert result["moc"] == "MOC-IA-LLMs"
    assert len(result["wikilinks"]) >= 1


def test_merge_orchestration_updates_title_and_links():
    analysis = {"tema": "Teste", "wikilinks": ["Legado"]}
    orchestration = {
        "titulo_nota": "Agentes LLM em Python — guia prático",
        "pasta": "ia-llms",
        "moc": "MOC-IA-LLMs",
        "wikilinks": ["AgentesLLM", "Python"],
        "conexoes": ["[[RAG]]"],
        "tags_extra": ["agentes"],
    }
    merged = merge_orchestration(analysis, orchestration)
    assert merged["titulo_nota"] == "Agentes LLM em Python — guia prático"
    assert merged["pasta"] == "ia-llms"
    assert "[[RAG]]" in merged["conexoes"]


def test_agente_orquestrador_uses_llm_json():
    analysis = {
        "tema": "Gateway local de IA",
        "topicos": [{"titulo": "Arquitetura", "pontos": ["Edge"]}],
        "termos": [{"termo": "Gateway", "definicao": "Roteador"}],
    }
    llm_json = """{
      "titulo_nota": "Gateway de IA soberano no edge",
      "pasta": "ia-llms",
      "moc": "MOC-IA-LLMs",
      "wikilinks": ["Gateway", "EdgeAI", "Ollama", "MLOps", "Soberania"],
      "conexoes": ["[[RAG]]", "[[DevOps]]"],
      "tags_extra": ["ia-local", "edge"]
    }"""

    with patch(
        "app.services.obsidian_orchestrator.ollama_generate",
        new_callable=AsyncMock,
        return_value=llm_json,
    ):
        import asyncio

        merged = asyncio.run(agente_orquestrador_obsidian(_sample_item(), analysis))

    assert merged["titulo_nota"] == "Gateway de IA soberano no edge"
    assert merged["pasta"] == "ia-llms"
