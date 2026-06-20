# Plan 009: Source Health Monitor — Painel de Status por Scraper

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/models.py backend/app/services/ingest.py backend/alembic/versions/
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P2
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none (se o plano 006 estiver em andamento e mudar o número da migration Alembic, ajuste `down_revision` deste plano)
- **Category**: feature, observability
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

Erros de scraper hoje são logados e descartados:

```python
# backend/app/services/ingest.py:198-203
except Exception as exc:
    message = f"{label}: {exc}"
    logger.warning("Scraper failed %s", message)
    # ← erro vai para o log e some; a UI não sabe
```

Não há como saber, via UI, se o Reddit scraper está falhando silenciosamente há 3 dias. O usuário só percebe quando nota ausência de artigos de uma fonte — difícil de diagnosticar.

**O que este plano faz**: adicionar uma tabela `scraper_runs` que registra cada execução de scraper (source, started_at, finished_at, items_found, error). Um endpoint `GET /api/system/health` expõe o estado atual de cada fonte — última coleta, quantos itens, status (ok/error). A coleta de dados acontece dentro do `_fetch_all_articles` existente, sem mudar a lógica de ingest.

## Current state

### `backend/app/services/ingest.py` — `_fetch_all_articles` (linhas 175-212)

```python
FETCHER_LABELS: dict[str, str] = {
    "fetch_devto": "dev.to",
    "fetch_reddit": "Reddit",
    "fetch_github_trends": "GitHub Trends",
    "fetch_hacker_news": "Hacker News",
    "fetch_rss_feeds": "RSS",
}


def _fetch_all_articles(
    fetchers: list[Fetcher],
    on_progress: ProgressEmitter | None = None,
) -> tuple[list[RawArticle], list[str]]:
    articles: list[RawArticle] = []
    errors: list[str] = []

    def run_fetcher(fetcher: Fetcher) -> tuple[list[RawArticle], str | None]:
        name = _fetcher_name(fetcher)
        label = FETCHER_LABELS.get(name, name)
        emit_step(on_progress, "fetch", "active", f"Buscando {label}…")
        try:
            batch = fetcher()
            emit_step(on_progress, "fetch", "active", f"{label}: {len(batch)} artigo(s)")
            return batch, None
        except Exception as exc:
            message = f"{label}: {exc}"
            logger.warning("Scraper failed %s", message)
            errors.append(message)
            return [], message
    ...
```

A função recebe `fetchers: list[Fetcher]` e `on_progress`. Não tem acesso à `db`. Para persistir os runs, precisamos passar `db` como argumento.

### `backend/app/services/ingest.py` — `run_ingest` (linha 605)

```python
def run_ingest(
    db: Session,
    fetchers: list[Fetcher] | None = None,
    enricher: Callable[[RawArticle], object] | None = None,
    on_progress: ProgressEmitter | None = None,
    cancel_event: threading.Event | None = None,
) -> dict:
    ...
    articles, scraper_errors = _fetch_all_articles(fetchers, on_progress)
```

`db` está disponível em `run_ingest` — só precisamos passá-lo para `_fetch_all_articles`.

### `backend/app/models.py`

`Base` é importado de `app.database`. Padrão de modelo:

```python
class TopicFolder(Base):
    __tablename__ = "topic_folders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### `backend/alembic/versions/004_add_missing_news_indexes.py` — padrão de migration

```python
revision = "004"
down_revision = "003"

def upgrade() -> None:
    op.create_index("idx_news_folder", "news_items", ["folder_id"])
    ...

def downgrade() -> None:
    op.drop_index("idx_news_folder", table_name="news_items")
    ...
```

**Nota sobre numeração**: o plano 006 cria migration `005`. Se o plano 006 for executado antes deste, use `down_revision = "005"`. Se este plano for executado primeiro (sem o 006), use `down_revision = "004"`. **Verifique com `cd backend && alembic current` antes de escrever o `down_revision`**.

### `backend/app/routes/health.py` — padrão de rota de sistema

```python
router = APIRouter(tags=["system"])

@router.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", service="techpulse")
```

## Scope

**In scope**:
- `backend/app/models.py` — adicionar modelo `ScraperRun`
- `backend/alembic/versions/006_add_scraper_runs.py` (ou `005_` se o plano 006 não foi executado — verificar)
- `backend/app/services/ingest.py` — modificar `_fetch_all_articles` para aceitar `db` e persistir runs
- `backend/app/routes/health.py` — adicionar endpoint `GET /api/system/health`
- `backend/app/schemas.py` — adicionar schemas `ScraperHealthResponse`, `SystemHealthResponse`

**Out of scope** (não tocar):
- `backend/app/routes/__init__.py` — health.router já está registrado
- Lógica de ingest além de `_fetch_all_articles` e a chamada em `run_ingest`
- Frontend — zero mudanças de frontend neste plano

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Check current migration | `cd backend && alembic current` | mostra revision atual |
| Run migrations | `cd backend && alembic upgrade head` | ok |
| Run tests | `cd backend && pytest -q` | all pass |
| Import check | `cd backend && python -c "from app.models import ScraperRun; print('ok')"` | ok |

## Steps

### Step 0: Verificar numeração da migration

```
cd backend && alembic current
```

Se mostrar `004`, use `down_revision = "004"` e nomeie o arquivo `005_add_scraper_runs.py`.
Se mostrar `005` (plano 006 executado), use `down_revision = "005"` e nomeie o arquivo `006_add_scraper_runs.py`.

O restante dos steps usa `005_add_scraper_runs.py` como exemplo — ajuste o nome se necessário.

### Step 1: Adicionar `ScraperRun` em `models.py`

Em `backend/app/models.py`, adicionar após a classe `NewsItem`:

```python
class ScraperRun(Base):
    __tablename__ = "scraper_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    items_found: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    __table_args__ = (
        Index("idx_scraper_runs_source", "source"),
        Index("idx_scraper_runs_started", "started_at"),
    )
```

Adicionar `ScraperRun` ao import em `backend/app/models.py`. Verificar que `Index` já está importado de `sqlalchemy`.

**Verify**: `cd backend && python -c "from app.models import ScraperRun; print('ok')"` → `ok`

### Step 2: Criar migration Alembic

Criar `backend/alembic/versions/005_add_scraper_runs.py` (ajuste número se necessário):

```python
"""Add scraper_runs table for source health monitoring

Revision ID: 005
Revises: 004
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"  # VERIFICAR com 'alembic current' antes de escrever
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.String, nullable=True),
    )
    op.create_index("idx_scraper_runs_source", "scraper_runs", ["source"])
    op.create_index("idx_scraper_runs_started", "scraper_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("idx_scraper_runs_started", table_name="scraper_runs")
    op.drop_index("idx_scraper_runs_source", table_name="scraper_runs")
    op.drop_table("scraper_runs")
```

**Verify**: `cd backend && alembic upgrade head` → mostra `Running upgrade`

### Step 3: Adicionar schemas em `schemas.py`

Em `backend/app/schemas.py`, adicionar antes do final do arquivo:

```python
class ScraperHealthResponse(BaseModel):
    source: str
    last_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_items_found: int = 0
    last_error: str | None = None
    status: str  # "ok" | "error" | "never_run"


class SystemHealthResponse(BaseModel):
    scrapers: list[ScraperHealthResponse]
    total_items: int
    relevant_items: int
```

### Step 4: Modificar `_fetch_all_articles` em `ingest.py` para aceitar `db`

Em `backend/app/services/ingest.py`, modificar a assinatura e o corpo de `_fetch_all_articles`:

```python
def _fetch_all_articles(
    fetchers: list[Fetcher],
    on_progress: ProgressEmitter | None = None,
    db: Session | None = None,      # ← novo parâmetro opcional
) -> tuple[list[RawArticle], list[str]]:
    articles: list[RawArticle] = []
    errors: list[str] = []

    if not fetchers:
        return articles, errors

    def run_fetcher(fetcher: Fetcher) -> tuple[list[RawArticle], str | None]:
        name = _fetcher_name(fetcher)
        label = FETCHER_LABELS.get(name, name)
        emit_step(on_progress, "fetch", "active", f"Buscando {label}…")
        
        started_at = datetime.now(timezone.utc)
        try:
            batch = fetcher()
            finished_at = datetime.now(timezone.utc)
            emit_step(on_progress, "fetch", "active", f"{label}: {len(batch)} artigo(s)")
            if db is not None:
                _record_scraper_run(db, source=label, started_at=started_at,
                                    finished_at=finished_at, items_found=len(batch), error=None)
            return batch, None
        except Exception as exc:
            finished_at = datetime.now(timezone.utc)
            message = f"{label}: {exc}"
            logger.warning("Scraper failed %s", message)
            errors.append(message)
            if db is not None:
                _record_scraper_run(db, source=label, started_at=started_at,
                                    finished_at=finished_at, items_found=0, error=str(exc)[:500])
            return [], message

    with ThreadPoolExecutor(max_workers=len(fetchers)) as pool:
        futures = [pool.submit(run_fetcher, f) for f in fetchers]
        for future in as_completed(futures):
            batch, error = future.result()
            articles.extend(batch)

    return articles, errors
```

Adicionar a função helper `_record_scraper_run` antes de `_fetch_all_articles`:

```python
def _record_scraper_run(
    db: Session,
    *,
    source: str,
    started_at: datetime,
    finished_at: datetime,
    items_found: int,
    error: str | None,
) -> None:
    from app.models import ScraperRun
    try:
        run = ScraperRun(
            source=source,
            started_at=started_at,
            finished_at=finished_at,
            items_found=items_found,
            error=error,
        )
        db.add(run)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to record scraper run: %s", exc)
        db.rollback()
```

E atualizar a chamada em `run_ingest` (linha ~638):

```python
articles, scraper_errors = _fetch_all_articles(fetchers, on_progress, db=db)
```

Verificar que `datetime` e `timezone` já estão importados em `ingest.py` (eles são usados na lógica de semantic dedup). Se não, adicionar ao topo.

**Verify**: `cd backend && python -c "from app.services.ingest import _fetch_all_articles, _record_scraper_run; print('ok')"` → `ok`

### Step 5: Adicionar endpoint `GET /api/system/health` em `routes/health.py`

Em `backend/app/routes/health.py`, adicionar ao final do arquivo:

```python
from datetime import datetime, timezone

from sqlalchemy import func, select, text

from app.database import get_db
from app.models import NewsItem, ScraperRun
from app.schemas import ScraperHealthResponse, SystemHealthResponse

_ALL_SOURCES = ["dev.to", "Reddit", "GitHub Trends", "Hacker News", "RSS"]


@router.get("/api/system/health", response_model=SystemHealthResponse)
def system_health(db: Session = Depends(get_db)):
    """Estado de saúde por fonte — última coleta, erros, total de itens."""
    scrapers: list[ScraperHealthResponse] = []

    for source in _ALL_SOURCES:
        last_run = db.scalar(
            select(ScraperRun)
            .where(ScraperRun.source == source)
            .order_by(ScraperRun.started_at.desc())
            .limit(1)
        )
        last_success = db.scalar(
            select(ScraperRun)
            .where(ScraperRun.source == source)
            .where(ScraperRun.error.is_(None))
            .order_by(ScraperRun.started_at.desc())
            .limit(1)
        )

        if last_run is None:
            status = "never_run"
        elif last_run.error is not None:
            status = "error"
        else:
            status = "ok"

        scrapers.append(ScraperHealthResponse(
            source=source,
            last_run_at=last_run.started_at if last_run else None,
            last_success_at=last_success.started_at if last_success else None,
            last_items_found=last_run.items_found if last_run else 0,
            last_error=last_run.error if last_run else None,
            status=status,
        ))

    total_items = db.scalar(select(func.count()).select_from(NewsItem)) or 0
    relevant_items = db.scalar(
        select(func.count()).select_from(NewsItem).where(NewsItem.ai_relevance == "RELEVANTE")
    ) or 0

    return SystemHealthResponse(
        scrapers=scrapers,
        total_items=total_items,
        relevant_items=relevant_items,
    )
```

Verificar que `Session` e `Depends` já estão importados em `health.py`. Se não, adicionar:

```python
from fastapi import Depends
from sqlalchemy.orm import Session
```

**Verify**: `cd backend && python -c "from app.routes.health import router; routes=[r.path for r in router.routes]; print('/api/system/health' in routes)"` → `True`

### Step 6: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

## Test plan

Adicionar `backend/tests/test_scraper_health.py`:

```python
"""Testes para o source health monitor."""
import pytest
from datetime import datetime, timezone

from app.models import ScraperRun
from app.schemas import ScraperHealthResponse, SystemHealthResponse


def test_scraper_run_model_creation():
    """ScraperRun pode ser instanciado com os campos esperados."""
    run = ScraperRun(
        source="dev.to",
        started_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        items_found=42,
        error=None,
    )
    assert run.source == "dev.to"
    assert run.items_found == 42
    assert run.error is None


def test_scraper_health_response_schema():
    response = ScraperHealthResponse(
        source="Reddit",
        last_run_at=datetime.now(timezone.utc),
        last_success_at=datetime.now(timezone.utc),
        last_items_found=10,
        last_error=None,
        status="ok",
    )
    assert response.status == "ok"


def test_scraper_health_error_status():
    response = ScraperHealthResponse(
        source="GitHub Trends",
        last_run_at=datetime.now(timezone.utc),
        last_success_at=None,
        last_items_found=0,
        last_error="Connection timeout",
        status="error",
    )
    assert response.status == "error"
    assert response.last_error == "Connection timeout"


def test_scraper_health_never_run():
    response = ScraperHealthResponse(
        source="Hacker News",
        last_run_at=None,
        last_success_at=None,
        last_items_found=0,
        last_error=None,
        status="never_run",
    )
    assert response.status == "never_run"
```

**Verify**: `cd backend && pytest tests/test_scraper_health.py -v` → todos passam

## Done criteria

- [ ] `backend/app/models.py` tem classe `ScraperRun`
- [ ] Migration `005_add_scraper_runs.py` (ou `006_`) existe em `backend/alembic/versions/`
- [ ] `cd backend && alembic upgrade head` → ok
- [ ] `grep -n "_record_scraper_run" backend/app/services/ingest.py` → 2+ matches (definição + chamada)
- [ ] `grep -n "db=db" backend/app/services/ingest.py` → inclui chamada de `_fetch_all_articles` com `db=db`
- [ ] `grep -n "/api/system/health" backend/app/routes/health.py` → 1 match
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_scraper_health.py -v` → all pass

## STOP conditions

Pare e reporte se:
- `alembic upgrade head` falhar por conflito de `down_revision` — significa que o plano 006 (FTS5) foi executado antes e criou a migration 005. Renomeie este arquivo para `006_add_scraper_runs.py` com `down_revision = "005"`.
- `_fetch_all_articles` não tiver os imports `datetime, timezone` disponíveis no escopo — verifique os imports no topo do `ingest.py` antes de usar em `_record_scraper_run`.
- `db.commit()` dentro de `_record_scraper_run` conflitar com a sessão principal de `run_ingest` — se isso ocorrer, use `db.flush()` em vez de `db.commit()` e deixe o commit para o final do ingest. Reporte antes de ajustar.

## Maintenance notes

- **Thread safety de `_record_scraper_run`**: `_fetch_all_articles` usa `ThreadPoolExecutor`. Múltiplos scrapers podem chamar `_record_scraper_run` concorrentemente. SQLAlchemy Session não é thread-safe para uso compartilhado — se houver erros de concorrência, crie uma nova Session dentro de `_record_scraper_run` usando `SessionLocal()` em vez de reusar `db`.
- **Retenção de histórico**: os runs acumulam indefinidamente. Para bancos de longa duração, considerar um job de limpeza que mantém apenas os últimos 30 dias de `scraper_runs`.
- **Label vs source**: `FETCHER_LABELS` mapeia nome da função para label legível. O `ScraperRun.source` usa o label (ex: "dev.to", "Reddit") — consistente com o que o usuário vê na UI.
