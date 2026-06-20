# Plan 002: Corrigir Queries que Carregam Toda a Tabela + Adicionar Índices Faltantes

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat b15548f..HEAD -- backend/app/services/ingest.py backend/app/models.py
> ```
> Se qualquer arquivo mudou, compare os excerpts de "Current state" contra o código live antes de prosseguir.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf
- **Planned at**: commit `b15548f`, 2026-06-20

## Why this matters

Dois padrões de query carregam ORM objects desnecessários em memória e depois os filtram em Python — uma anti-pattern clássica de SQLAlchemy. Em um banco com 10 mil artigos RELEVANTE, isso resulta em dezenas de MB de alocação e centenas de ms de latência só para _contar_ itens de backfill. Paralelamente, há apenas um índice composto na tabela `news_items`, mas as queries de filtro mais comuns (`folder_id`, `source`, `obsidian_exported_at`) não têm índice — causando full table scans que escalam linearmente com o crescimento do banco.

## Current state

### Problema 1: `_count_legacy_enrichment` — filtro em Python (`backend/app/services/ingest.py:219-226`)

```python
# ingest.py:219-226 — estado atual
def _count_legacy_enrichment(db: Session) -> int:
    items = db.scalars(
        select(NewsItem)              # ← carrega objetos ORM completos
        .where(NewsItem.is_enriched.is_(True))
        .where(NewsItem.ai_relevance == "RELEVANTE")
    ).all()                           # ← all() materializa TUDO na memória
    return sum(1 for item in items if needs_agent_refresh(item))  # ← filtra em Python
```

O predicado real que define "precisa refresh" está em `needs_agent_refresh()`:
```python
# ingest.py:210-216
def needs_agent_refresh(item: NewsItem) -> bool:
    if not item.is_enriched or item.ai_relevance != "RELEVANTE":
        return False
    reasoning = (item.ai_reasoning or "").strip()
    if not reasoning:
        return True
    return "Novidade" not in reasoning or "Utilidade" not in reasoning
```

Em SQL, isso equivale a: `ai_reasoning IS NULL OR ai_reasoning = '' OR ai_reasoning NOT LIKE '%Novidade%' OR ai_reasoning NOT LIKE '%Utilidade%'`

### Problema 2: `re_enrich_legacy_items` — carrega tudo, depois fatia (`backend/app/services/ingest.py:887-893`)

```python
# ingest.py:887-893 — estado atual
def re_enrich_legacy_items(db, limit=10, on_progress=None):
    candidates_before = _count_legacy_enrichment(db)
    all_candidates = db.scalars(        # ← carrega TODOS os candidatos
        select(NewsItem)
        .where(NewsItem.is_enriched.is_(True))
        .where(NewsItem.ai_relevance == "RELEVANTE")
        .order_by(NewsItem.created_at.desc())
    ).all()
    items = [item for item in all_candidates if needs_agent_refresh(item)][:limit]  # ← filtra e fatia em Python
```

### Problema 3: Índices faltantes (`backend/app/models.py:56`)

```python
# models.py:56 — estado atual
__table_args__ = (Index("idx_news_unread", "is_read", "ai_relevance"),)
```

Apenas **um** índice. As queries de filtro mais frequentes no `apply_news_filters()` (`backend/app/repositories/news.py:46-79`) usam:
- `folder_id` — sem índice
- `source` — sem índice  
- `obsidian_exported_at IS NOT NULL / IS NULL` — sem índice
- `hype_score >= N` — sem índice
- `created_at DESC` (ORDER BY) — sem índice

### Convenções do projeto

- SQLAlchemy 2.0 style: `select(Model).where(...)`, não `.query()`.
- Alembic para todas as mudanças de schema. Ver `backend/alembic/versions/` para padrão de migration file.
- Alembic import pattern (ver qualquer migration existente): `from alembic import op; import sqlalchemy as sa`.
- `needs_agent_refresh()` deve ser mantida para uso no enriquecimento individual (não remover).

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run all tests | `cd backend && pytest -q` | all pass |
| Run specific test | `cd backend && pytest tests/test_legacy_enrich.py -v` | all pass |
| Check Alembic | `cd backend && alembic current` | shows current revision |
| Apply migration | `cd backend && alembic upgrade head` | exit 0 |
| Downgrade migration | `cd backend && alembic downgrade -1` | exit 0 |
| Generate migration | `cd backend && alembic revision --autogenerate -m "add indexes"` | creates file |

## Scope

**In scope**:
- `backend/app/services/ingest.py` — somente as funções `_count_legacy_enrichment` e `re_enrich_legacy_items`
- `backend/app/models.py` — somente `__table_args__` em `NewsItem`
- `backend/alembic/versions/` — um novo migration file (criar via alembic)

**Out of scope** (não tocar):
- `needs_agent_refresh()` — usada em outros lugares, não alterar a assinatura nem o comportamento
- `backend/app/repositories/news.py` — não faz parte deste plano
- Qualquer rota ou endpoint
- `_count_pending()` (ingest.py:194-207) — já usa `func.count()` corretamente, não tocar

## Git workflow

- Branch: `advisor/002-db-perf-indexes-pushdown`
- 3 commits: `perf: push _count_legacy_enrichment filter to SQL`, `perf: push re_enrich_legacy_items limit to SQL`, `perf: add missing indexes on news_items`
- Não fazer push nem abrir PR sem instrução.

## Steps

### Step 1: Refatorar `_count_legacy_enrichment` para usar SQL WHERE

Em `backend/app/services/ingest.py`, substituir a função `_count_legacy_enrichment` (linhas 219-225) pela versão abaixo. A query equivale exatamente a `needs_agent_refresh()` em SQL:

```python
def _count_legacy_enrichment(db: Session) -> int:
    from sqlalchemy import or_
    return (
        db.scalar(
            select(func.count())
            .select_from(NewsItem)
            .where(NewsItem.is_enriched.is_(True))
            .where(NewsItem.ai_relevance == "RELEVANTE")
            .where(
                or_(
                    NewsItem.ai_reasoning.is_(None),
                    NewsItem.ai_reasoning == "",
                    NewsItem.ai_reasoning.notlike("%Novidade%"),
                    NewsItem.ai_reasoning.notlike("%Utilidade%"),
                )
            )
        )
        or 0
    )
```

> **Nota importante**: a função `needs_agent_refresh()` permanece inalterada — ainda é usada em `re_enrich_legacy_items` para verificação item a item após o fetch. Esta mudança só altera a função de *contagem*.

**Verify**: `cd backend && python -c "from app.services.ingest import _count_legacy_enrichment; print('ok')"` → prints `ok`

### Step 2: Refatorar `re_enrich_legacy_items` para usar SQL LIMIT

Em `backend/app/services/ingest.py`, substituir as linhas 887-893 (a query de `all_candidates` e a linha `items = ...`) pela versão com LIMIT no SQL. A função já recebe `limit` como parâmetro.

**Estado atual (linhas 887-895):**
```python
    all_candidates = db.scalars(
        select(NewsItem)
        .where(NewsItem.is_enriched.is_(True))
        .where(NewsItem.ai_relevance == "RELEVANTE")
        .order_by(NewsItem.created_at.desc())
    ).all()
    items = [item for item in all_candidates if needs_agent_refresh(item)][:limit]
```

**Estado alvo:**
```python
    from sqlalchemy import or_
    items = list(
        db.scalars(
            select(NewsItem)
            .where(NewsItem.is_enriched.is_(True))
            .where(NewsItem.ai_relevance == "RELEVANTE")
            .where(
                or_(
                    NewsItem.ai_reasoning.is_(None),
                    NewsItem.ai_reasoning == "",
                    NewsItem.ai_reasoning.notlike("%Novidade%"),
                    NewsItem.ai_reasoning.notlike("%Utilidade%"),
                )
            )
            .order_by(NewsItem.created_at.desc())
            .limit(limit)
        ).all()
    )
```

> Remover a linha `items = [item for item in all_candidates if needs_agent_refresh(item)][:limit]` e a variável `all_candidates`. O `needs_agent_refresh()` no loop de processamento mais abaixo na função não precisa mudar — já recebe os items corretos.

**Verify**: `cd backend && pytest tests/test_legacy_enrich.py -v` → all pass

**Verify**: `cd backend && pytest tests/test_hype_backfill.py -v` → all pass

### Step 3: Adicionar índices faltantes no modelo

Em `backend/app/models.py`, expandir `__table_args__` em `NewsItem` (linha 56):

**Estado atual:**
```python
__table_args__ = (Index("idx_news_unread", "is_read", "ai_relevance"),)
```

**Estado alvo:**
```python
__table_args__ = (
    Index("idx_news_unread", "is_read", "ai_relevance"),
    Index("idx_news_folder", "folder_id"),
    Index("idx_news_source", "source"),
    Index("idx_news_obsidian", "obsidian_exported_at"),
    Index("idx_news_hype", "hype_score"),
    Index("idx_news_created", "created_at"),
)
```

**Verify**: `cd backend && python -c "from app.models import NewsItem; print([str(i) for i in NewsItem.__table_args__])"` → lista com 6 índices

### Step 4: Criar migration Alembic para os novos índices

O projeto usa Alembic para mudanças de schema. Os índices adicionados no Step 3 precisam de um migration file para aplicar em bancos existentes.

Criar o arquivo de migration manualmente (não use `--autogenerate` se o banco de desenvolvimento já tem os índices aplicados via `create_all`). Crie um arquivo em `backend/alembic/versions/` seguindo o padrão dos existentes:

```python
# backend/alembic/versions/<timestamp>_add_missing_news_indexes.py
"""add missing news_items indexes

Revision ID: <gere um hex aleatório de 12 chars, ex: a1b2c3d4e5f6>
Revises: <revision ID da migration mais recente em alembic/versions/>
Create Date: 2026-06-20
"""
from alembic import op

revision = "<seu hex aqui>"
down_revision = "<revision ID da última migration>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_news_folder", "news_items", ["folder_id"])
    op.create_index("idx_news_source", "news_items", ["source"])
    op.create_index("idx_news_obsidian", "news_items", ["obsidian_exported_at"])
    op.create_index("idx_news_hype", "news_items", ["hype_score"])
    op.create_index("idx_news_created", "news_items", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_news_created", table_name="news_items")
    op.drop_index("idx_news_hype", table_name="news_items")
    op.drop_index("idx_news_obsidian", table_name="news_items")
    op.drop_index("idx_news_source", table_name="news_items")
    op.drop_index("idx_news_folder", table_name="news_items")
```

Para obter o `down_revision` correto: `cd backend && alembic current` ou `alembic history` para ver a revision mais recente.

**Verify**: `cd backend && alembic upgrade head` → exit 0, sem errors

**Verify**: `cd backend && alembic downgrade -1 && alembic upgrade head` → ambos exit 0 (round-trip ok)

### Step 5: Rodar suite completa

**Verify**: `cd backend && pytest -q` → all pass, 0 failures

## Test plan

Os testes existentes em `backend/tests/test_legacy_enrich.py` cobrem o comportamento de `re_enrich_legacy_items`. Confirmar que passam após os refactors.

Se quiser adicionar um teste de regressão para o count pushdown:

```python
# backend/tests/test_legacy_enrich.py — adicionar
def test_count_legacy_enrichment_uses_sql_not_python(db_session, monkeypatch):
    """_count_legacy_enrichment não deve chamar needs_agent_refresh em Python."""
    call_count = 0
    original = ingest.needs_agent_refresh
    def tracking_refresh(item):
        nonlocal call_count
        call_count += 1
        return original(item)
    monkeypatch.setattr(ingest, "needs_agent_refresh", tracking_refresh)
    
    ingest._count_legacy_enrichment(db_session)
    assert call_count == 0, "needs_agent_refresh foi chamada — count ainda filtra em Python"
```

Pattern a seguir: `backend/tests/test_legacy_enrich.py` (fixture `db_session` de `conftest.py`).

**Verify**: `cd backend && pytest tests/test_legacy_enrich.py -v` → all pass

## Done criteria

- [ ] `cd backend && pytest -q` exits 0
- [ ] `grep -n "\.all().*needs_agent_refresh" backend/app/services/ingest.py` → 0 matches (filtragem Python removida)
- [ ] `grep -n "all_candidates" backend/app/services/ingest.py` → 0 matches
- [ ] `backend/app/models.py` contém 6 entradas em `__table_args__`
- [ ] `cd backend && alembic upgrade head` exits 0
- [ ] `cd backend && alembic downgrade -1 && alembic upgrade head` exits 0
- [ ] Nenhum arquivo fora da lista **In scope** foi modificado (`git diff --name-only`)
- [ ] `plans/README.md` status row atualizada para DONE

## STOP conditions

Pare e reporte se:
- Os excerpts de `_count_legacy_enrichment` (linhas 219-225) não baterem com o código atual (drift).
- Os excerpts de `re_enrich_legacy_items` (linhas 887-893) não baterem.
- `alembic upgrade head` falhar — não improvise o schema; reporte o erro.
- Qualquer teste em `test_legacy_enrich.py` ou `test_hype_backfill.py` falhar após os refactors.
- A variável `all_candidates` aparecer em outros locais do arquivo (fora das linhas mapeadas) — reporte antes de remover.

## Maintenance notes

- **Critério de "precisa refresh" pode mudar**: se o formato de `ai_reasoning` mudar (ex: se "Novidade"/"Utilidade" forem renomeados), tanto `needs_agent_refresh()` quanto a query SQL equivalente neste plano precisam ser atualizadas em sincronia.
- **Índices e Alembic**: novos campos em `NewsItem` que forem usados em filtros devem sempre ter um índice correspondente — adicione em `__table_args__` e crie a migration.
- **Dual migration**: este projeto tem tanto Alembic quanto `migrate_sqlite_schema()` em `models.py`. Os índices novos serão criados pelo Alembic. A função `migrate_sqlite_schema()` não precisa ser atualizada (ela trata apenas colunas, não índices). Consolidar os dois sistemas em Alembic puro está planejado mas não faz parte deste plano.
