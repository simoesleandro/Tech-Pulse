# Plan 011: Digest Semanal por Webhook JSON (Slack, Discord, N8N, Zapier)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/services/settings.py backend/app/schemas.py backend/app/routes/settings.py
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P3
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: feature
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

O único output de digest hoje é Obsidian (`/api/obsidian/digest`). Para quem não usa Obsidian — ou quer receber um resumo sem abrir o app — não há alternativa.

Um webhook configurable (POST para uma URL com JSON) resolve isso com esforço baixo e cobre um universo grande de destinos: Slack, Discord, Teams, N8N, Zapier, Make, ou qualquer endpoint HTTP. O usuário configura a URL do webhook nas Settings e aciona via `POST /api/digest/send`.

**O que este plano não faz**: não envia automaticamente (sem cron embutido). O envio é manual ou pode ser agendado externamente via N8N/Zapier. Isso reduz complexidade e evita armazenar credenciais de email.

## Current state

### `backend/app/schemas.py:200-211` — `AppSettings`

```python
class SourcesSettings(BaseModel):
    dev_to: bool
    reddit: bool
    github_trends: bool
    hacker_news: bool
    rss_feeds: bool


class AppSettings(BaseModel):
    background_ingest_enabled: bool
    obsidian_auto_export: bool = False
    pipeline_mode: str = "unified"
    sources: SourcesSettings
```

`AppSettings` não tem campo para webhook URL. Este plano adiciona `digest_webhook_url: str | None = None`.

### `backend/app/services/settings.py` — `DEFAULT_SETTINGS`

```python
DEFAULT_SETTINGS: dict = AppSettings(
    background_ingest_enabled=False,
    obsidian_auto_export=False,
    pipeline_mode="unified",
    sources={
        "dev_to": True,
        "reddit": True,
        "github_trends": True,
        "hacker_news": True,
        "rss_feeds": True,
    },
).model_dump()
```

Adicionar `digest_webhook_url=None` ao construtor.

### `backend/app/routes/settings.py` — rota de settings

```python
# Verificar o conteúdo atual:
# grep -n "def " backend/app/routes/settings.py
```

Executar antes de prosseguir para ver as funções existentes.

### `backend/requirements.txt`

`httpx` já está listado — será usado para o POST do webhook.

### `backend/app/repositories/news.py:88-105` — `list_news_filtered`

Já funciona para filtrar por `ai_relevance`, `is_read`, `min_hype`. O digest usará para buscar itens relevantes dos últimos N dias.

## Scope

**In scope**:
- `backend/app/schemas.py` — adicionar `digest_webhook_url: str | None = None` ao `AppSettings`
- `backend/app/services/settings.py` — adicionar `digest_webhook_url=None` ao `DEFAULT_SETTINGS`
- `backend/app/services/digest.py` — criar novo arquivo com a lógica de geração e envio
- `backend/app/routes/digest.py` — criar novo arquivo com `POST /api/digest/send` e `GET /api/digest/preview`
- `backend/app/routes/__init__.py` — registrar o router de digest

**Out of scope** (não tocar):
- `backend/app/services/obsidian.py` — o digest Obsidian não muda
- Email SMTP — fora do escopo deste plano (maior complexidade de credenciais)
- Envio automático / cron — fora do escopo

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run tests | `cd backend && pytest -q` | all pass |
| Import check | `cd backend && python -c "from app.services.digest import build_digest_payload; print('ok')"` | ok |
| Settings check | `cd backend && python -c "from app.schemas import AppSettings; s = AppSettings.model_validate({'background_ingest_enabled': False, 'obsidian_auto_export': False, 'pipeline_mode': 'unified', 'sources': {'dev_to': True, 'reddit': True, 'github_trends': True, 'hacker_news': True, 'rss_feeds': True}}); print(s.digest_webhook_url)"` | `None` |

## Steps

### Step 0: Verificar `routes/settings.py` antes de modificar

```
cat backend/app/routes/settings.py
```

Anotar as funções existentes para não sobrescrever nada ao modificar o schema.

### Step 1: Adicionar `digest_webhook_url` ao schema

Em `backend/app/schemas.py`, modificar `AppSettings`:

```python
class AppSettings(BaseModel):
    background_ingest_enabled: bool
    obsidian_auto_export: bool = False
    pipeline_mode: str = "unified"
    sources: SourcesSettings
    digest_webhook_url: str | None = None  # ← adicionar esta linha
```

Em `backend/app/services/settings.py`, modificar `DEFAULT_SETTINGS`:

```python
DEFAULT_SETTINGS: dict = AppSettings(
    background_ingest_enabled=False,
    obsidian_auto_export=False,
    pipeline_mode="unified",
    digest_webhook_url=None,  # ← adicionar
    sources={
        "dev_to": True,
        "reddit": True,
        "github_trends": True,
        "hacker_news": True,
        "rss_feeds": True,
    },
).model_dump()
```

**Verify**: `cd backend && python -c "from app.schemas import AppSettings; s = AppSettings.model_validate({'background_ingest_enabled': False, 'obsidian_auto_export': False, 'pipeline_mode': 'unified', 'sources': {'dev_to': True, 'reddit': True, 'github_trends': True, 'hacker_news': True, 'rss_feeds': True}}); print(s.digest_webhook_url)"` → `None`

**Verify**: `cd backend && pytest tests/test_settings_validation.py -v` → all pass (o campo novo tem default, não quebra testes existentes)

### Step 2: Criar `backend/app/services/digest.py`

```python
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
```

**Verify**: `cd backend && python -c "from app.services.digest import build_digest_payload, collect_digest_items, send_webhook; print('ok')"` → `ok`

### Step 3: Criar `backend/app/routes/digest.py`

```python
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
```

**Verify**: `cd backend && python -c "from app.routes.digest import router; print('ok')"` → `ok`

### Step 4: Registrar o router

Em `backend/app/routes/__init__.py`:

```python
from app.routes import backfill, digest, feed, health, ingest, news, obsidian, settings

__all__ = ["health", "news", "ingest", "obsidian", "settings", "backfill", "feed", "digest"]


def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(news.router)
    app.include_router(ingest.router)
    app.include_router(obsidian.router)
    app.include_router(settings.router)
    app.include_router(backfill.router)
    app.include_router(feed.router)     # se plano 008 foi executado; remover se não
    app.include_router(digest.router)
```

**Nota**: se o plano 008 (RSS Output Feed) NÃO foi executado, omitir `feed` do import e do `register_routes`. Não copiar a linha de `feed` se ela não existir.

**Verify**: `cd backend && python -c "
from app.routes import register_routes
from fastapi import FastAPI
app = FastAPI()
register_routes(app)
paths = [r.path for r in app.routes]
print('/api/digest/send' in paths)
print('/api/digest/preview' in paths)
"` → ambos `True`

### Step 5: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

## Test plan

Adicionar `backend/tests/test_digest.py`:

```python
"""Testes para geração de digest."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.digest import build_digest_payload, _source_label
from app.models import NewsItem


def _make_item(**kwargs) -> NewsItem:
    item = object.__new__(NewsItem)
    defaults = {
        "id": 1,
        "title": "Article PT",
        "title_original": "Article EN",
        "url": "https://example.com",
        "source": "hacker_news",
        "description": "Description",
        "ai_reasoning": "This is relevant",
        "hype_score": 3,
        "ai_relevance": "RELEVANTE",
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


def test_build_digest_payload_structure():
    item = _make_item()
    payload = build_digest_payload([item], days=7)
    assert "articles" in payload
    assert "slack_text" in payload
    assert "article_count" in payload
    assert payload["article_count"] == 1


def test_build_digest_payload_empty():
    payload = build_digest_payload([], days=7)
    assert payload["article_count"] == 0
    assert payload["articles"] == []


def test_slack_text_contains_title():
    item = _make_item(title="Python 3.13 Released")
    payload = build_digest_payload([item], days=7)
    assert "Python 3.13 Released" in payload["slack_text"]


def test_source_label_rss():
    assert _source_label("rss/cloudflare-blog") == "Cloudflare Blog"


def test_source_label_known():
    assert _source_label("hacker_news") == "Hacker News"


def test_source_label_unknown():
    assert _source_label("unknown_source") == "unknown_source"
```

**Verify**: `cd backend && pytest tests/test_digest.py -v` → todos passam

## Done criteria

- [ ] `grep -n "digest_webhook_url" backend/app/schemas.py` → 1 match
- [ ] `grep -n "digest_webhook_url" backend/app/services/settings.py` → 1 match
- [ ] `backend/app/services/digest.py` existe com funções `build_digest_payload`, `collect_digest_items`, `send_webhook`
- [ ] `backend/app/routes/digest.py` existe com endpoints `/api/digest/send` e `/api/digest/preview`
- [ ] `grep -n "digest" backend/app/routes/__init__.py` → 2+ matches
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_settings_validation.py tests/test_digest.py -v` → all pass

## STOP conditions

Pare e reporte se:
- `test_settings_validation.py` falhar após adicionar `digest_webhook_url` — indica que o teste verifica os campos exatos do schema. Verifique o conteúdo do arquivo antes de reportar.
- `send_webhook` falhar com `SSLError` em ambiente de dev — esperado para webhooks em localhost; não bloqueia o plano.
- `list_news_filtered` não aceitar `q=None` — indica mudança de assinatura pelo plano 006. Leia o estado atual antes de prosseguir.

## Maintenance notes

- **Slack Incoming Webhooks**: o payload `{"text": "..."}` é o formato correto. Para blocos avançados (Block Kit), adaptar `build_digest_payload` para incluir um campo `blocks`.
- **Discord Webhooks**: usa `content` em vez de `text`. Limite de 2000 chars — o `slack_text` pode precisar ser truncado para Discord.
- **N8N/Zapier**: recebem o payload completo como JSON. O `articles` array tem todos os campos necessários para automação (url, title, hype_score, etc.).
- **Segurança da URL**: `digest_webhook_url` é armazenado no `settings.json`. Em produção, considerar usar variável de ambiente para não expor tokens de webhook no arquivo de settings.
