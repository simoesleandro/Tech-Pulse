"""RSS 2.0 output feed — artigos RELEVANTE dos últimos 7 dias."""
import re
from datetime import datetime, timedelta, timezone
from xml.etree.ElementTree import Element, SubElement, tostring

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import NewsItem
from app.repositories.news import list_news_filtered

router = APIRouter(tags=["feed"])

_SOURCE_LABELS = {
    "dev.to": "Dev.to",
    "reddit": "Reddit",
    "github_trends": "GitHub Trends",
    "hacker_news": "Hacker News",
}


def _source_label(source: str) -> str:
    if source.startswith("rss/"):
        return source[4:].replace("-", " ").title()
    return _SOURCE_LABELS.get(source, source)


def _rfc822(dt: datetime) -> str:
    """Formata datetime como RFC 822 para RSS pubDate."""
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _sanitize(text: str | None) -> str:
    """Remove caracteres XML inválidos."""
    if not text:
        return ""
    # Remove control characters exceto tab, newline, carriage return
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)


def build_rss_feed(items: list[NewsItem], *, days: int = 7) -> bytes:
    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "TechPulse — Engineering Intelligence Feed"
    SubElement(channel, "description").text = (
        f"Artigos relevantes para engenheiros de software — últimos {days} dias"
    )
    SubElement(channel, "language").text = "pt-BR"
    SubElement(channel, "lastBuildDate").text = _rfc822(datetime.now(timezone.utc))

    for item in items:
        entry = SubElement(channel, "item")
        SubElement(entry, "title").text = _sanitize(item.title)
        SubElement(entry, "link").text = _sanitize(item.url)
        SubElement(entry, "guid", isPermaLink="true").text = _sanitize(item.url)
        SubElement(entry, "pubDate").text = _rfc822(item.created_at)

        source_label = _source_label(item.source)
        description_parts = []
        if item.description:
            description_parts.append(_sanitize(item.description))
        if item.ai_reasoning:
            description_parts.append(f"\n\n💡 {_sanitize(item.ai_reasoning)}")
        description_parts.append(f"\n\n📡 Fonte: {source_label} | Hype: {'⭐' * item.hype_score}")

        SubElement(entry, "description").text = "".join(description_parts)

        SubElement(entry, "source", url="").text = source_label

    return tostring(rss, encoding="utf-8", xml_declaration=True)


@router.get("/api/feed.rss")
def get_rss_feed(
    days: int = Query(default=7, ge=1, le=30),
    min_hype: int = Query(default=0, ge=0, le=5),
    source: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Feed RSS dos artigos relevantes. Não requer autenticação."""
    items, _ = list_news_filtered(
        db,
        limit=100,
        offset=0,
        ai_relevance="RELEVANTE",
        is_read=None,
        is_bookmarked=None,
        folder_id=None,
        source=source,
        min_hype=min_hype if min_hype > 0 else None,
        hype=None,
        obsidian_exported=None,
        q=None,
    )

    # Filtrar por janela de dias
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent_items = [i for i in items if i.created_at >= cutoff]

    xml_bytes = build_rss_feed(recent_items, days=days)
    return Response(
        content=xml_bytes,
        media_type="application/rss+xml; charset=utf-8",
    )
