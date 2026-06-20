"""Geração e envio de digest semanal via webhook JSON."""
import logging
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from app.models import NewsItem
from app.repositories.news import list_news_filtered

logger = logging.getLogger(__name__)

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


def build_digest_payload(items: list[NewsItem], *, days: int = 7) -> dict:
    """Monta o payload JSON para envio via webhook.

    O formato é genérico (N8N, Zapier, webhooks custom) mas inclui um campo
    `slack_text` pré-formatado para uso direto com Slack Incoming Webhooks.
    """
    articles = [
        {
            "id": item.id,
            "title": item.title,
            "title_original": item.title_original,
            "url": item.url,
            "source": _source_label(item.source),
            "hype_score": item.hype_score,
            "summary": item.ai_reasoning or item.description or "",
            "published_at": item.created_at.isoformat(),
        }
        for item in items
    ]

    # Texto pré-formatado para Slack
    slack_lines = [f"*TechPulse Digest — últimos {days} dias* ({len(articles)} artigos)\n"]
    for art in articles[:10]:  # Slack tem limite de mensagem
        stars = "⭐" * art["hype_score"] if art["hype_score"] > 0 else ""
        slack_lines.append(f"• <{art['url']}|{art['title']}> {stars}")
        if art["summary"]:
            slack_lines.append(f"  _{art['summary'][:100]}..._")
    slack_text = "\n".join(slack_lines)

    return {
        "digest_type": "techpulse_weekly",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": days,
        "article_count": len(articles),
        "articles": articles,
        "slack_text": slack_text,  # pronto para Slack Incoming Webhook
    }


def collect_digest_items(
    db: Session,
    *,
    days: int = 7,
    min_hype: int = 0,
) -> list[NewsItem]:
    """Coleta artigos relevantes dos últimos `days` dias."""
    items, _ = list_news_filtered(
        db,
        limit=200,
        offset=0,
        ai_relevance="RELEVANTE",
        is_read=None,
        is_bookmarked=None,
        folder_id=None,
        source=None,
        min_hype=min_hype if min_hype > 0 else None,
        hype=None,
        obsidian_exported=None,
        q=None,
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return [i for i in items if i.created_at >= cutoff]


def send_webhook(url: str, payload: dict, *, timeout: float = 15.0) -> dict:
    """Envia o payload para a URL de webhook configurada.

    Compatível com Slack Incoming Webhooks (usa `text` = slack_text),
    Discord Webhooks (usa `content` = slack_text), e webhooks genéricos.
    """
    # Detecta destino e adapta o payload se necessário
    is_slack = "hooks.slack.com" in url
    is_discord = "discord.com/api/webhooks" in url

    if is_slack:
        send_payload = {"text": payload["slack_text"]}
    elif is_discord:
        send_payload = {"content": payload["slack_text"]}
    else:
        send_payload = payload  # payload completo para N8N/Zapier/custom

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, json=send_payload)
        response.raise_for_status()

    return {"status": "sent", "http_status": response.status_code}
