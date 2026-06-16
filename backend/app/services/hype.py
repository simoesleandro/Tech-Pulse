import math

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
        raw = 2.0

    return min(5, max(0, round(raw)))
