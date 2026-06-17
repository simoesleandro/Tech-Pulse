import asyncio
from unittest.mock import AsyncMock, patch

from app.services.ai_agent import orquestrador_enriquecimento
from app.services.scrapers.base import EnrichedArticle, RawArticle


def test_orquestrador_skip_triador_skips_classifier():
    article = RawArticle(
        title="Python async patterns",
        url="https://example.com/async",
        source="dev.to",
        description_snippet="Guide to asyncio",
    )

    with (
        patch("app.services.ai_agent.agente_triador", new_callable=AsyncMock) as triador,
        patch(
            "app.services.ai_agent.agente_tradutor",
            new_callable=AsyncMock,
            return_value=("Padrões async em Python", "Guia de asyncio."),
        ),
        patch(
            "app.services.ai_agent.agente_hype",
            new_callable=AsyncMock,
            return_value=type(
                "A",
                (),
                {
                    "hype": 3,
                    "reasoning": "Novidade 2 · Utilidade 4 · Comunidade 2 — ok",
                    "novelty": 2,
                    "practicality": 4,
                    "community_signal": 2,
                },
            )(),
        ),
    ):
        enriched = asyncio.run(
            orquestrador_enriquecimento(article, skip_triador=True)
        )

    triador.assert_not_called()
    assert enriched.ai_relevance == "RELEVANTE"
    assert enriched.title_pt == "Padrões async em Python"
