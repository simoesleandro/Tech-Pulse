import math
from datetime import datetime, timezone

from app.services.scrapers.base import RawArticle


def compute_hype_score(article: RawArticle) -> int:
    if article.source == "dev.to":
        raw = article.positive_reactions * 0.12 + article.comments_count * 0.2
    elif article.source == "github_trends":
        raw = math.log10(max(article.stars, 0) + 1) * 1.75
    elif article.source == "reddit":
        raw = math.log10(max(article.ups, 0) + 1) * 2.1
    elif article.source == "hacker_news":
        raw = math.log10(max(article.ups, 0) + 1) * 2.3 + article.comments_count * 0.05
    else:
        # RSS feeds — sem engagement social; usa sinais de qualidade do feed
        raw = _rss_hype(article)

    return min(5, max(0, math.floor(raw + 0.5)))


def _rss_hype(article: RawArticle) -> float:
    """Calcula hype para fontes RSS usando sinais de qualidade.

    Base: 2.0 (mantém backward compat para feeds sem metadados)
    Bônus de frescor: +1.0 se publicado há menos de 24h
    Bônus de substância: +1.0 se content_length > 2000 chars (artigo longo)
    Bônus de substância maior: +1.5 se content_length > 5000 chars (artigo denso)
    Máximo efetivo: 4.5 antes do cap de 5
    """
    score = 2.0

    # Bônus de frescor
    if article.pub_date is not None:
        age_hours = (datetime.now(timezone.utc) - article.pub_date).total_seconds() / 3600
        if 0 <= age_hours < 24:
            score += 1.0
        elif age_hours < 0:
            # pub_date no futuro — ignorar (dado inválido)
            pass

    # Bônus de substância (tamanho do conteúdo como proxy de profundidade)
    if article.content_length >= 5000:
        score += 1.5
    elif article.content_length >= 2000:
        score += 1.0

    return score
