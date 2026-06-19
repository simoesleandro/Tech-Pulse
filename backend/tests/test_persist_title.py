from app.services.ingest import resolve_persist_title
from app.services.scrapers.base import RawArticle


def test_resolve_persist_title_github_trends():
    article = RawArticle(
        title="vinta/awesome-python",
        url="https://github.com/vinta/awesome-python",
        source="github_trends",
    )
    assert resolve_persist_title(article, "vinta/awesome-python") == "Vinta - Awesome Python"


def test_resolve_persist_title_other_sources_unchanged():
    article = RawArticle(
        title="Some title",
        url="https://example.com/a",
        source="dev.to",
    )
    assert resolve_persist_title(article, "Título traduzido") == "Título traduzido"
