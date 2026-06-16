from dataclasses import dataclass


@dataclass(frozen=True)
class RawArticle:
    title: str
    url: str
    source: str
    description_snippet: str = ""
    positive_reactions: int = 0
    comments_count: int = 0
    stars: int = 0
    ups: int = 0


@dataclass(frozen=True)
class EnrichedArticle:
    ai_relevance: str
    title_pt: str
    description_pt: str
    hype_score: int
    ai_reasoning: str | None = None
