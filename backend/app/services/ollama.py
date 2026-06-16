"""Facade de compatibilidade — delega ao orquestrador multi-agente."""

from app.services.ai_agent import (
    agente_hype,
    agente_tradutor,
    agente_triador,
    enrich_article_sync,
    orquestrador_enriquecimento,
)
from app.services.scrapers.base import EnrichedArticle, RawArticle

__all__ = [
    "agente_hype",
    "agente_tradutor",
    "agente_triador",
    "enrich_article",
    "enrich_article_sync",
    "orquestrador_enriquecimento",
    "classify_title",
]


def enrich_article(article: RawArticle) -> EnrichedArticle:
    return enrich_article_sync(article)


def classify_title(title: str) -> str:
    article = RawArticle(title=title, url="https://local/classify", source="local")
    return enrich_article_sync(article).ai_relevance
