"""Endpoints para geração e envio de digest."""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_api_key
from app.services.digest import build_digest_payload, collect_digest_items, send_webhook
from app.services.settings import load_settings

logger = logging.getLogger(__name__)
router = APIRouter(tags=["digest"])


class DigestSendResult(BaseModel):
    sent: bool
    article_count: int
    http_status: int | None = None
    error: str | None = None


class DigestPreviewResult(BaseModel):
    article_count: int
    period_days: int
    articles: list[dict]
    slack_text: str


@router.get("/api/digest/preview", response_model=DigestPreviewResult, dependencies=[Depends(require_api_key)])
def preview_digest(
    days: int = Query(default=7, ge=1, le=30),
    min_hype: int = Query(default=0, ge=0, le=5),
    db: Session = Depends(get_db),
):
    """Pré-visualiza o digest sem enviar."""
    items = collect_digest_items(db, days=days, min_hype=min_hype)
    payload = build_digest_payload(items, days=days)
    return DigestPreviewResult(
        article_count=payload["article_count"],
        period_days=days,
        articles=payload["articles"][:20],  # limite para preview
        slack_text=payload["slack_text"],
    )


@router.post("/api/digest/send", response_model=DigestSendResult, dependencies=[Depends(require_api_key)])
def send_digest(
    days: int = Query(default=7, ge=1, le=30),
    min_hype: int = Query(default=0, ge=0, le=5),
    db: Session = Depends(get_db),
):
    """Gera e envia o digest para o webhook configurado nas Settings."""
    settings = load_settings()
    webhook_url = settings.get("digest_webhook_url")

    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Webhook URL não configurada. Defina digest_webhook_url nas Settings.",
        )

    items = collect_digest_items(db, days=days, min_hype=min_hype)
    payload = build_digest_payload(items, days=days)

    try:
        result = send_webhook(webhook_url, payload)
        return DigestSendResult(
            sent=True,
            article_count=payload["article_count"],
            http_status=result["http_status"],
        )
    except Exception as exc:
        logger.error("Digest webhook failed: %s", exc)
        return DigestSendResult(
            sent=False,
            article_count=payload["article_count"],
            error=str(exc)[:200],
        )
