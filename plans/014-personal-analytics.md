# Plan 014: Personal Analytics — GET /api/analytics

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/routes/news.py backend/app/repositories/news.py
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P3
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: feature, ux
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

Todos os dados de engajamento estão no banco — mas o usuário não tem visibilidade:
- Quais fontes têm melhor taxa de relevância para ele?
- Quais tecnologias aparecem mais nos artigos que ele marcou como RELEVANTE?
- Quando o pipeline tem mais artigos (para saber se ingest está funcionando)?
- Quais pastas cresceram mais esta semana?

Um endpoint `GET /api/analytics` com agregações simples do SQLAlchemy responde isso sem lógica complexa. Zero dependências extras — é puro SQL com GROUP BY.

## Current state

### `backend/app/models.py` — campos disponíveis para analytics

```python
class NewsItem(Base):
    source: str          # "dev.to" | "reddit" | "github_trends" | "hacker_news" | "rss/..."
    ai_relevance: str    # "RELEVANTE" | "LIXO" | "PENDING"
    user_relevance: str | None  # "RELEVANTE" | "LIXO" | "TALVEZ" | None
    is_read: bool
    is_bookmarked: bool
    hype_score: int      # 0-5
    folder_id: int | None
    created_at: datetime
```

### `backend/app/repositories/news.py:1` — imports disponíveis

```python
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload
```

### `backend/app/routes/health.py` — padrão de rota simples para seguir

```python
router = APIRouter(tags=["system"])

@router.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", service="techpulse")
```

### `backend/app/routes/__init__.py` — como registrar nova rota

```python
from app.routes import backfill, health, ingest, news, obsidian, settings

def register_routes(app: FastAPI) -> None:
    app.include_router(health.router)
    ...
```

## Scope

**In scope**:
- `backend/app/schemas.py` — adicionar schemas de analytics
- `backend/app/services/analytics.py` — criar: queries de agregação
- `backend/app/routes/analytics.py` — criar: `GET /api/analytics`
- `backend/app/routes/__init__.py` — registrar router de analytics

**Out of scope** (não tocar):
- `backend/app/models.py` — sem novas colunas
- Migrations Alembic — sem mudanças de schema
- Frontend — zero mudanças de UI neste plano

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run tests | `cd backend && pytest -q` | all pass |
| Import check | `cd backend && python -c "from app.services.analytics import get_analytics; print('ok')"` | ok |
| Route check | `cd backend && python -c "from app.routes.analytics import router; paths=[r.path for r in router.routes]; print('/api/analytics' in paths)"` | True |

## Steps

### Step 1: Adicionar schemas ao `schemas.py`

Em `backend/app/schemas.py`, adicionar antes do final do arquivo:

```python
class SourceStats(BaseModel):
    source: str
    total: int
    relevante: int
    relevance_rate: float  # relevante / total (0.0-1.0)
    avg_hype: float


class IngestByDay(BaseModel):
    date: str  # "YYYY-MM-DD"
    total: int
    relevante: int


class FolderStats(BaseModel):
    folder_id: int | None
    folder_name: str | None
    item_count: int


class AnalyticsResponse(BaseModel):
    period_days: int
    total_items: int
    relevant_items: int
    read_items: int
    bookmarked_items: int
    feedback_given: int
    sources: list[SourceStats]
    ingest_by_day: list[IngestByDay]
    top_folders: list[FolderStats]
```

### Step 2: Criar `backend/app/services/analytics.py`

```python
"""Agregações para o painel de analytics pessoal."""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, func, select, text
from sqlalchemy.orm import Session, joinedload

from app.models import NewsItem, TopicFolder
from app.schemas import AnalyticsResponse, FolderStats, IngestByDay, SourceStats

logger = logging.getLogger(__name__)


def get_analytics(db: Session, *, days: int = 30) -> AnalyticsResponse:
    """Calcula métricas de uso dos últimos `days` dias."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Totais gerais
    base_filter = NewsItem.created_at >= cutoff
    total_items = db.scalar(
        select(func.count()).select_from(NewsItem).where(base_filter)
    ) or 0
    relevant_items = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.ai_relevance == "RELEVANTE")
    ) or 0
    read_items = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.is_read.is_(True))
    ) or 0
    bookmarked_items = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.is_bookmarked.is_(True))
    ) or 0
    feedback_given = db.scalar(
        select(func.count()).select_from(NewsItem)
        .where(base_filter)
        .where(NewsItem.user_relevance.isnot(None))
    ) or 0

    # Stats por fonte
    source_rows = db.execute(
        select(
            NewsItem.source,
            func.count().label("total"),
            func.sum(
                case((NewsItem.ai_relevance == "RELEVANTE", 1), else_=0)
            ).label("relevante"),
            func.avg(NewsItem.hype_score).label("avg_hype"),
        )
        .where(base_filter)
        .group_by(NewsItem.source)
        .order_by(func.count().desc())
        .limit(20)
    ).fetchall()

    sources: list[SourceStats] = []
    for row in source_rows:
        total = row.total or 0
        relevante = row.relevante or 0
        sources.append(SourceStats(
            source=row.source,
            total=total,
            relevante=relevante,
            relevance_rate=round(relevante / total, 3) if total > 0 else 0.0,
            avg_hype=round(float(row.avg_hype or 0), 2),
        ))

    # Ingest por dia — SQLite: strftime para truncar ao dia
    day_rows = db.execute(
        text(
            """
            SELECT
                strftime('%Y-%m-%d', created_at) AS day,
                COUNT(*) AS total,
                SUM(CASE WHEN ai_relevance = 'RELEVANTE' THEN 1 ELSE 0 END) AS relevante
            FROM news_items
            WHERE created_at >= :cutoff
            GROUP BY day
            ORDER BY day DESC
            LIMIT :days
            """
        ),
        {"cutoff": cutoff.isoformat(), "days": days},
    ).fetchall()

    ingest_by_day: list[IngestByDay] = [
        IngestByDay(date=row.day, total=row.total or 0, relevante=row.relevante or 0)
        for row in day_rows
    ]

    # Top pastas por número de itens
    folder_rows = db.execute(
        select(
            NewsItem.folder_id,
            TopicFolder.name.label("folder_name"),
            func.count().label("item_count"),
        )
        .outerjoin(TopicFolder, NewsItem.folder_id == TopicFolder.id)
        .where(base_filter)
        .where(NewsItem.is_bookmarked.is_(True))
        .group_by(NewsItem.folder_id, TopicFolder.name)
        .order_by(func.count().desc())
        .limit(10)
    ).fetchall()

    top_folders: list[FolderStats] = [
        FolderStats(
            folder_id=row.folder_id,
            folder_name=row.folder_name,
            item_count=row.item_count or 0,
        )
        for row in folder_rows
    ]

    return AnalyticsResponse(
        period_days=days,
        total_items=total_items,
        relevant_items=relevant_items,
        read_items=read_items,
        bookmarked_items=bookmarked_items,
        feedback_given=feedback_given,
        sources=sources,
        ingest_by_day=ingest_by_day,
        top_folders=top_folders,
    )
```

**Verify**: `cd backend && python -c "from app.services.analytics import get_analytics; print('ok')"` → `ok`

### Step 3: Criar `backend/app/routes/analytics.py`

```python
"""Endpoint de analytics pessoal."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps.auth import require_api_key
from app.schemas import AnalyticsResponse
from app.services.analytics import get_analytics

router = APIRouter(tags=["analytics"])


@router.get("/api/analytics", response_model=AnalyticsResponse, dependencies=[Depends(require_api_key)])
def analytics(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Métricas de uso pessoal — fontes, ingest por dia, pastas."""
    return get_analytics(db, days=days)
```

**Verify**: `cd backend && python -c "from app.routes.analytics import router; print('ok')"` → `ok`

### Step 4: Registrar o router

Em `backend/app/routes/__init__.py`, adicionar `analytics`:

```python
from app.routes import analytics, backfill, health, ingest, news, obsidian, settings
# (adicionar também feed e digest se os planos 008/011 foram executados)

__all__ = [..., "analytics"]


def register_routes(app: FastAPI) -> None:
    ...
    app.include_router(analytics.router)  # adicionar ao final
```

**Verify**: `cd backend && python -c "
from app.routes import register_routes
from fastapi import FastAPI
app = FastAPI()
register_routes(app)
paths = [r.path for r in app.routes]
print('/api/analytics' in paths)
"` → `True`

### Step 5: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

## Test plan

Adicionar `backend/tests/test_analytics.py`:

```python
"""Testes para o serviço de analytics."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.schemas import AnalyticsResponse, SourceStats


def test_analytics_response_schema():
    """Schema de response aceita os campos esperados."""
    response = AnalyticsResponse(
        period_days=30,
        total_items=100,
        relevant_items=40,
        read_items=25,
        bookmarked_items=10,
        feedback_given=5,
        sources=[],
        ingest_by_day=[],
        top_folders=[],
    )
    assert response.total_items == 100
    assert response.relevant_items == 40


def test_source_stats_relevance_rate():
    """relevance_rate é calculado corretamente."""
    stats = SourceStats(
        source="hacker_news",
        total=100,
        relevante=40,
        relevance_rate=0.4,
        avg_hype=3.2,
    )
    assert stats.relevance_rate == 0.4


def test_get_analytics_returns_response():
    """get_analytics retorna AnalyticsResponse mesmo com banco vazio."""
    from app.database import SessionLocal
    from app.services.analytics import get_analytics
    db = SessionLocal()
    try:
        result = get_analytics(db, days=7)
        assert isinstance(result, AnalyticsResponse)
        assert result.period_days == 7
        assert result.total_items >= 0
    finally:
        db.close()


def test_get_analytics_sources_ordered_by_total():
    """Fontes são ordenadas por total decrescente."""
    from app.database import SessionLocal
    from app.services.analytics import get_analytics
    db = SessionLocal()
    try:
        result = get_analytics(db, days=365)
        if len(result.sources) > 1:
            assert result.sources[0].total >= result.sources[1].total
    finally:
        db.close()
```

**Verify**: `cd backend && pytest tests/test_analytics.py -v` → todos passam

## Done criteria

- [ ] `grep -n "AnalyticsResponse\|SourceStats\|IngestByDay\|FolderStats" backend/app/schemas.py` → 4+ matches
- [ ] `backend/app/services/analytics.py` existe com função `get_analytics`
- [ ] `backend/app/routes/analytics.py` existe com endpoint `/api/analytics`
- [ ] `grep -n "analytics" backend/app/routes/__init__.py` → 2+ matches
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_analytics.py -v` → all pass

## STOP conditions

Pare e reporte se:
- `case()` do SQLAlchemy retornar erro de importação — use `from sqlalchemy import case` e verifique a sintaxe para SQLAlchemy 2.0 (que pode diferir do 1.x).
- A query `strftime` com `text()` lançar `OperationalError` — verifique se o `cutoff.isoformat()` está no formato correto para SQLite (`YYYY-MM-DDTHH:MM:SS`).
- `func.sum(case(...))` retornar `None` em vez de `0` — adicionar `or 0` na atribuição.

## Maintenance notes

- **SQLAlchemy 2.0 `case()`**: a sintaxe é `case((condition, value), else_=default)` — diferente do 1.x que usava `case([(condition, value)], else_=default)`. Verifique a versão instalada com `python -c "import sqlalchemy; print(sqlalchemy.__version__)"`.
- **Performance**: as queries usam `WHERE created_at >= cutoff` — coberto pelo índice `idx_news_created`. A query de dia-a-dia usa `text()` com SQL raw (SQLite não tem `DATE_TRUNC` nativo, só `strftime`).
- **Extensões futuras**: adicionar `GET /api/analytics/export` que retorna CSV para planilhas. Adicionar filtro por source para analytics de uma fonte específica.
