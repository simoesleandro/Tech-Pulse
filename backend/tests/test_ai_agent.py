import asyncio
from unittest.mock import AsyncMock, patch

from app.services.ai_agent import (
    _parse_relevance,
    _parse_tradutor_response,
    agente_triador,
    orquestrador_enriquecimento,
)
from app.services.scrapers.base import RawArticle


def test_parse_relevance():
    assert _parse_relevance("RELEVANTE") == "RELEVANTE"
    assert _parse_relevance("LIXO") == "LIXO"
    assert _parse_relevance("Isso é LIXO para o feed") == "LIXO"
    assert _parse_relevance("ambíguo") == "LIXO"


def test_parse_tradutor_json_fallback():
    article = RawArticle(
        title="Original title",
        url="https://example.com/a",
        source="dev.to",
        description_snippet="snippet",
    )
    raw = '{"titulo_pt": "Título PT", "descricao_pt": "Descrição em português."}'
    title_pt, desc_pt = _parse_tradutor_response(raw, article)
    assert title_pt == "Título PT"
    assert desc_pt == "Descrição em português."


def test_agente_triador_relevante():
    article = RawArticle(
        title="Python async patterns",
        url="https://example.com/async",
        source="dev.to",
        description_snippet="Deep dive into asyncio",
    )

    with patch(
        "app.services.ai_agent.ollama_generate",
        new_callable=AsyncMock,
        return_value="RELEVANTE",
    ):
        result = asyncio.run(agente_triador(article))

    assert result == "RELEVANTE"


def test_orquestrador_lixo_skips_tradutor_and_hype():
    article = RawArticle(
        title="Celebrity gossip",
        url="https://example.com/gossip",
        source="reddit",
    )

    with patch(
        "app.services.ai_agent.ollama_generate",
        new_callable=AsyncMock,
        return_value="LIXO",
    ) as mock_generate:
        enriched = asyncio.run(orquestrador_enriquecimento(article))

    assert enriched.ai_relevance == "LIXO"
    assert enriched.hype_score == 0
    assert enriched.title_pt == article.title
    mock_generate.assert_called_once()


def test_orquestrador_relevante_runs_all_agents():
    article = RawArticle(
        title="Building LLM agents with Python",
        url="https://example.com/llm",
        source="dev.to",
        description_snippet="Agent orchestration guide",
        positive_reactions=42,
        comments_count=7,
    )
    responses = [
        "RELEVANTE",
        '{"titulo_pt": "Construindo agentes LLM com Python", "descricao_pt": "Guia de orquestração."}',
        "HYPE: 4",
    ]

    with patch(
        "app.services.ai_agent.ollama_generate",
        new_callable=AsyncMock,
        side_effect=responses,
    ) as mock_generate:
        enriched = asyncio.run(orquestrador_enriquecimento(article))

    assert enriched.ai_relevance == "RELEVANTE"
    assert enriched.title_pt == "Construindo agentes LLM com Python"
    assert enriched.description_pt == "Guia de orquestração."
    assert enriched.hype_score >= 1
    assert mock_generate.call_count == 3
