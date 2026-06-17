import asyncio
from unittest.mock import patch

from app.services.ai_agent import enrich_articles_parallel
from app.services.scrapers.base import RawArticle


def test_enrich_articles_parallel_processes_batch():
    articles = [
        RawArticle(title=f"Article {index}", url=f"https://example.com/{index}", source="dev.to")
        for index in range(3)
    ]

    async def fake_orquestrador(article, on_agent_progress=None, **kwargs):
        from app.services.scrapers.base import EnrichedArticle

        return EnrichedArticle(
            ai_relevance="RELEVANTE",
            title_pt=article.title,
            description_pt="Resumo.",
            hype_score=3,
            ai_reasoning="Impacto moderado.",
        )

    with patch("app.services.ai_agent.orquestrador_enriquecimento", side_effect=fake_orquestrador):
        results = asyncio.run(enrich_articles_parallel(articles))

    assert len(results) == 3
    assert all(not isinstance(outcome, Exception) for _, _, outcome in results)
    assert all(outcome.hype_score == 3 for _, _, outcome in results)
