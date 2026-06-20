# Plan 008: RSS Output Feed — /api/feed.rss

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/routes/ backend/app/main.py
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: feature
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

O TechPulse coleta e filtra conteúdo de múltiplas fontes — mas o único output estruturado é a exportação para Obsidian. Engenheiros que usam leitores de RSS (Reeder, NetNewsWire, Feedly, Inoreader) não podem assinar o próprio feed filtrado sem abrir o app.

Um endpoint `GET /api/feed.rss` que retorna os artigos `RELEVANTE` dos últimos 7 dias como RSS 2.0 resolve isso com esforço S: a lógica de filtro já existe, o formato RSS é XML simples, e a biblioteca `xml.etree.ElementTree` está na stdlib.

O feed pode ser consumido por:
- Qualquer leitor de RSS
- N8N / Zapier / Make (triggers automáticos)
- Outros serviços de automação

## Current state

### Endpoints existentes (de `backend/app/routes/__init__.py`)

```python
from app.routes import backfill, health, ingest, news, obsidian, settings

def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(news.router)
    app.include_router(ingest.router)
    app.include_router(obsidian.router)
    app.include_router(settings.router)
    app.include_router(backfill.router)
```

Não existe rota de feed ainda.

### `backend/app/repositories/news.py:88-105` — `list_news_filtered` já funciona

```python
def list_news_filtered(
    db: Session,
    *,
    limit: int,
    offset: int,
    **filters,
) -> tuple[list[NewsItem], int]:
    ...
    items = db.scalars(
        base.order_by(NewsItem.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total
```

### `backend/app/models.py` — campos úteis para o feed

```python
class NewsItem(Base):
    id: int
    title: str           # título em português
    title_original: str  # título original
    url: str             # link externo
    source: str          # "dev.to", "reddit", "github_trends", "hacker_news", "rss/..."
    ai_relevance: str    # "RELEVANTE" | "LIXO" | "PENDING"
    hype_score: int      # 0-5
    ai_reasoning: str | None  # análise do LLM
    description: str     # descrição em português
    created_at: datetime
```

### `backend/app/deps/auth.py`

O `require_api_key` exige `X-API-Key` header. O feed RSS deve ser público (sem autenticação) para funcionar em leitores externos — não adicionar `Depends(require_api_key)`.

### CORS (de `backend/app/main.py`)

```python
allow_origins=config.cors_origins
```

O feed será acessado por leitores externos — não precisa de CORS, pois é consumido diretamente (não via fetch do browser). Se necessário, o usuário pode configurar `cors_origins=["*"]` no `.env`.

### Convenção de rota — `backend/app/routes/health.py`

```python
router = APIRouter(tags=["system"])

@router.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", service="techpulse")
```

O novo arquivo de rota deve seguir este padrão.

## Scope

**In scope**:
- `backend/app/routes/feed.py` — criar novo arquivo
- `backend/app/routes/__init__.py` — registrar o router de feed

**Out of scope** (não tocar):
- `backend/app/repositories/news.py` — reutilizar sem mudanças
- `backend/app/models.py` — sem mudanças
- `backend/requirements.txt` — a lib `xml.etree.ElementTree` é stdlib
- Frontend — zero mudanças; o feed é consumido por leitores externos

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run tests | `cd backend && pytest -q` | all pass |
| Import check | `cd backend && python -c "from app.routes.feed import router; print('ok')"` | ok |
| Route check | `cd backend && python -c "from app.routes import register_routes; from fastapi import FastAPI; app=FastAPI(); register_routes(app); routes=[r.path for r in app.routes]; print('/api/feed.rss' in routes)"` | `True` |

## Steps

### Step 1: Criar `backend/app/routes/feed.py`

```python
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
```

**Verify**: `cd backend && python -c "from app.routes.feed import router, build_rss_feed; print('ok')"` → `ok`

### Step 2: Registrar o router em `__init__.py`

Em `backend/app/routes/__init__.py`, adicionar `feed` ao import e ao `register_routes`:

```python
from app.routes import backfill, feed, health, ingest, news, obsidian, settings

__all__ = ["health", "news", "ingest", "obsidian", "settings", "backfill", "feed"]


def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    app.include_router(news.router)
    app.include_router(ingest.router)
    app.include_router(obsidian.router)
    app.include_router(settings.router)
    app.include_router(backfill.router)
    app.include_router(feed.router)
```

**Verify**: `cd backend && python -c "
from app.routes import register_routes
from fastapi import FastAPI
app = FastAPI()
register_routes(app)
paths = [r.path for r in app.routes]
print('/api/feed.rss' in paths)
"` → `True`

### Step 3: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

### Step 4: Teste de sanidade do XML

```
cd backend && python -c "
from app.routes.feed import build_rss_feed
from app.models import NewsItem
from datetime import datetime, timezone

# Item sintético para testar
item = NewsItem.__new__(NewsItem)
item.title = 'Test: Python 3.13 lançado'
item.url = 'https://example.com/python313'
item.source = 'hacker_news'
item.description = 'Python 3.13 traz novos recursos de performance'
item.ai_reasoning = 'Relevante para engenheiros Python.'
item.hype_score = 4
item.created_at = datetime.now(timezone.utc)

xml = build_rss_feed([item])
print(xml[:500].decode())
"
```

→ Imprime XML RSS válido sem exceção.

## Test plan

Adicionar `backend/tests/test_feed.py`:

```python
"""Testes para o endpoint RSS output feed."""
import pytest
from xml.etree.ElementTree import fromstring

from app.routes.feed import build_rss_feed, _rfc822, _sanitize
from app.models import NewsItem
from datetime import datetime, timezone


def _make_item(**kwargs) -> NewsItem:
    item = object.__new__(NewsItem)
    defaults = {
        "id": 1,
        "title": "Test Article",
        "title_original": "Test Article",
        "url": "https://example.com/test",
        "source": "hacker_news",
        "description": "A test article",
        "ai_reasoning": "This is relevant because...",
        "hype_score": 3,
        "ai_relevance": "RELEVANTE",
        "is_read": False,
        "is_bookmarked": False,
        "created_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(item, k, v)
    return item


def test_build_rss_feed_valid_xml():
    item = _make_item()
    xml_bytes = build_rss_feed([item])
    root = fromstring(xml_bytes)  # levanta se XML inválido
    assert root.tag == "rss"


def test_build_rss_feed_has_channel():
    xml_bytes = build_rss_feed([])
    root = fromstring(xml_bytes)
    channel = root.find("channel")
    assert channel is not None


def test_build_rss_feed_item_fields():
    item = _make_item(title="My Article", url="https://example.com/my")
    xml_bytes = build_rss_feed([item])
    root = fromstring(xml_bytes)
    rss_item = root.find("channel/item")
    assert rss_item is not None
    assert rss_item.find("title").text == "My Article"
    assert rss_item.find("link").text == "https://example.com/my"


def test_sanitize_removes_control_chars():
    result = _sanitize("hello\x00world\x1Ftest")
    assert "\x00" not in result
    assert "\x1F" not in result
    assert "helloworld" in result


def test_sanitize_empty():
    assert _sanitize(None) == ""
    assert _sanitize("") == ""


def test_build_rss_empty_list():
    xml_bytes = build_rss_feed([])
    root = fromstring(xml_bytes)
    items = root.findall("channel/item")
    assert items == []
```

**Verify**: `cd backend && pytest tests/test_feed.py -v` → todos passam

## Done criteria

- [ ] `backend/app/routes/feed.py` existe
- [ ] `grep -n "feed" backend/app/routes/__init__.py` → 2+ matches (import + include_router)
- [ ] `grep -n "/api/feed.rss" backend/app/routes/feed.py` → 1 match
- [ ] `grep -n "require_api_key" backend/app/routes/feed.py` → 0 matches (feed é público)
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_feed.py -v` → all pass
- [ ] XML produzido por `build_rss_feed` é parseável por `xml.etree.ElementTree.fromstring`

## STOP conditions

Pare e reporte se:
- `list_news_filtered` não aceitar `q=None` sem erro — indica mudança de assinatura em outro plano (ex: plano 006). Leia o estado atual da função antes de prosseguir.
- O XML gerado não for parseável por `fromstring` — debug o `build_rss_feed` com o item sintético do Step 4 antes de abrir PR.
- A rota `/api/feed.rss` colidir com outra rota existente — verifique `grep -rn "feed" backend/app/routes/`.

## Maintenance notes

- **Parâmetros do feed**: `days`, `min_hype`, `source` permitem ao usuário configurar a URL do feed no leitor RSS para filtrar por fonte ou hype mínimo. Ex: `/api/feed.rss?min_hype=4&source=github_trends`.
- **Sem autenticação**: intencional — leitores RSS externos não enviam headers. Se segurança for necessária, considerar token na URL query string (ex: `?token=<uuid>`).
- **Encoding XML**: `tostring(..., encoding="utf-8", xml_declaration=True)` garante o `<?xml version='1.0' encoding='utf-8'?>` no início, necessário para leitores RSS.
- **Limite de 100 itens**: suficiente para feeds diários/semanais. Para uso com `days=30`, pode aumentar para 200 se necessário.
