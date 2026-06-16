from dataclasses import dataclass


@dataclass(frozen=True)
class RawArticle:
    title: str
    url: str
    source: str
