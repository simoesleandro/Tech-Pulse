from app.services.article_content import fetch_article_context
from app.models import NewsItem
from datetime import datetime, timezone
from unittest.mock import patch


def _item(url: str, source: str = "dev.to") -> NewsItem:
    return NewsItem(
        id=1,
        title="Test",
        title_original="Test",
        description="Resumo.",
        url=url,
        source=source,
        ai_relevance="RELEVANTE",
        hype_score=3,
        is_enriched=True,
        is_read=False,
        is_bookmarked=False,
        created_at=datetime.now(timezone.utc),
    )


def test_fetch_article_context_uses_devto_api():
    with patch(
        "app.services.article_content._fetch_devto_body",
        return_value="# Markdown\n\nConteúdo longo do artigo.",
    ):
        context, chars, _body = fetch_article_context(_item("https://dev.to/author/my-post"))

    assert "Conteúdo longo do artigo." in context
    assert chars > 0


def test_fetch_article_context_falls_back_to_url_fetch():
    with patch("app.services.article_content._fetch_devto_body", return_value=""), patch(
        "app.services.article_content._fetch_url_text",
        return_value="Texto extraído da página.",
    ):
        context, _chars, _body = fetch_article_context(_item("https://example.com/post", source="rss"))

    assert "Texto extraído da página." in context
