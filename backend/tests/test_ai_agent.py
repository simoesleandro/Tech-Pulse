import asyncio
from unittest.mock import AsyncMock, patch

from app.services.ai_agent import (
    _parse_hype_response,
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


def test_parse_hype_json_response():
    raw = (
        '{"hype": 3, "novelty": 2, "practicality": 4, "community_signal": 3, '
        '"reasoning": "Tema técnico relevante, mas impacto moderado na comunidade."}'
    )
    assessment = _parse_hype_response(raw)
    assert assessment.hype == 3
    assert assessment.novelty == 2
    assert assessment.practicality == 4
    assert assessment.community_signal == 3
    assert "Novidade 2" in assessment.reasoning
    assert "Utilidade 4" in assessment.reasoning
    assert "moderado" in assessment.reasoning


def test_parse_hype_json_legacy_without_rubric():
    raw = '{"hype": 4, "reasoning": "Guia prático com alto interesse."}'
    assessment = _parse_hype_response(raw)
    assert assessment.hype == 4
    assert "Novidade 4" in assessment.reasoning
    assert "Utilidade 3" in assessment.reasoning
    assert "Guia prático" in assessment.reasoning


def test_parse_hype_non_json_fallback_includes_rubric():
    raw = "HYPE: 4\nImpacto alto na comunidade."
    assessment = _parse_hype_response(raw)
    assert assessment.hype == 4
    assert "Novidade 4" in assessment.reasoning
    assert "Utilidade 3" in assessment.reasoning


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
        "app.services.settings.load_settings",
        return_value={"pipeline_mode": "multi-agent"},
    ), patch(
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
        '{"hype": 4, "novelty": 3, "practicality": 4, "community_signal": 4, '
        '"reasoning": "Guia prático com alto interesse da comunidade Python."}',
    ]

    with patch(
        "app.services.settings.load_settings",
        return_value={"pipeline_mode": "multi-agent"},
    ), patch(
        "app.services.ai_agent.ollama_generate",
        new_callable=AsyncMock,
        side_effect=responses,
    ) as mock_generate:
        enriched = asyncio.run(orquestrador_enriquecimento(article))

    assert enriched.ai_relevance == "RELEVANTE"
    assert enriched.title_pt == "Construindo agentes LLM com Python"
    assert enriched.description_pt == "Guia de orquestração."
    assert enriched.hype_score == 4
    assert enriched.ai_reasoning is not None
    assert "Utilidade 4" in enriched.ai_reasoning
    assert mock_generate.call_count == 3

    hype_call = mock_generate.call_args_list[2]
    assert hype_call.kwargs.get("options") == {"temperature": 0.15, "num_predict": 1024}
    hype_prompt = hype_call.args[0]
    assert "Guia de orquestração." in hype_prompt
    assert "Score de engajamento pré-calculado" in hype_prompt


def test_agente_unificado_relevante():
    article = RawArticle(
        title="Building LLM agents with Python",
        url="https://example.com/llm",
        source="dev.to",
        description_snippet="Agent orchestration guide",
        positive_reactions=42,
        comments_count=7,
    )
    raw_response = (
        '{"relevance": "RELEVANTE", '
        '"titulo_pt": "Construindo agentes LLM com Python", '
        '"descricao_pt": "Guia de orquestração.", '
        '"hype": 4, "novelty": 3, "practicality": 4, "community_signal": 4, '
        '"reasoning": "Guia prático."}'
    )

    from app.services.ai_agent import agente_unificado
    with patch(
        "app.services.ai_agent.ollama_generate",
        new_callable=AsyncMock,
        return_value=raw_response,
    ) as mock_generate:
        enriched = asyncio.run(agente_unificado(article))

    assert enriched.ai_relevance == "RELEVANTE"
    assert enriched.title_pt == "Construindo agentes LLM com Python"
    assert enriched.description_pt == "Guia de orquestração."
    assert enriched.hype_score == 4
    assert "Novidade 3" in enriched.ai_reasoning
    mock_generate.assert_called_once()


def test_orquestrador_unified_mode():
    article = RawArticle(
        title="Building LLM agents with Python",
        url="https://example.com/llm",
        source="dev.to",
        description_snippet="Agent orchestration guide",
    )
    raw_response = (
        '{"relevance": "RELEVANTE", '
        '"titulo_pt": "Construindo agentes LLM com Python", '
        '"descricao_pt": "Guia de orquestração.", '
        '"hype": 4, "novelty": 3, "practicality": 4, "community_signal": 4, '
        '"reasoning": "Guia prático."}'
    )

    with patch(
        "app.services.settings.load_settings",
        return_value={"pipeline_mode": "unified"},
    ), patch(
        "app.services.ai_agent.ollama_generate",
        new_callable=AsyncMock,
        return_value=raw_response,
    ) as mock_generate:
        enriched = asyncio.run(orquestrador_enriquecimento(article))

    assert enriched.ai_relevance == "RELEVANTE"
    assert enriched.title_pt == "Construindo agentes LLM com Python"
    assert enriched.hype_score == 4
    assert mock_generate.call_count == 1

