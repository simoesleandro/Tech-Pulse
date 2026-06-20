# Plan 006: Upgrade Busca Textual de ILIKE para SQLite FTS5

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/repositories/news.py backend/app/models.py backend/alembic/versions/
> ```
> Se qualquer arquivo mudou, compare os excerpts de "Current state" antes de prosseguir.

## Status

- **Priority**: P1
- **Effort**: M
- **Risk**: LOW
- **Depends on**: none
- **Category**: perf, ux
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

O parâmetro `q` já existe na API (`GET /api/news?q=...`) e no repositório. A implementação atual usa `ILIKE` sobre três colunas:

```python
# backend/app/repositories/news.py:70-77 — estado atual
if q:
    pattern = f"%{q.strip()}%"
    query = query.where(
        or_(
            NewsItem.title.ilike(pattern),
            NewsItem.title_original.ilike(pattern),
            NewsItem.description.ilike(pattern),
        )
    )
```

Problemas concretos:
1. **Performance**: `ILIKE '%termo%'` não usa índice — full table scan a cada busca. Com 5.000+ itens, já é perceptível.
2. **Sem ranking por relevância**: um artigo que tem o termo no título aparece na mesma posição que um com o termo no final do description.
3. **Sem stemming**: buscar "kubernetes" não encontra "Kubernetes deployment" porque SQLite ILIKE é case-insensitive mas não tokeniza.

SQLite tem suporte nativo a FTS5 (Full-Text Search) — tabela virtual que indexa o texto, suporta ranking por BM25, e é acessível via SQL normal. Zero dependências extras.

**O que este plano faz**: criar uma tabela virtual `news_fts` sincronizada com `news_items`, substituir o ILIKE por uma query FTS5 com `rank` como critério de ordenação quando `q` está presente.

## Current state

### `backend/app/repositories/news.py` (linhas relevantes)

```python
# Linha 1-5: imports
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import NewsItem
from app.schemas import NewsItemResponse

# Linha 33-79: apply_news_filters — o parâmetro q já existe
def apply_news_filters(
    query,
    *,
    is_read: bool | None,
    is_bookmarked: bool | None,
    ai_relevance: str | None,
    folder_id: int | None,
    source: str | None,
    min_hype: int | None,
    hype: int | None,
    obsidian_exported: bool | None,
    q: str | None,
):
    ...
    if q:
        pattern = f"%{q.strip()}%"
        query = query.where(
            or_(
                NewsItem.title.ilike(pattern),
                NewsItem.title_original.ilike(pattern),
                NewsItem.description.ilike(pattern),
            )
        )
    return query
```

### `backend/app/routes/news.py` (linhas 38-100)

O parâmetro `q` já é declarado em `count_news` e `list_news`:

```python
q: str | None = Query(default=None, min_length=1, max_length=120),
```

A rota já passa `q=q` para `list_news_filtered` e `count_news_filtered`. **Não precisará ser alterada**.

### `backend/app/models.py`

`NewsItem.__tablename__ = "news_items"`. Colunas relevantes para FTS: `title` (str), `title_original` (str), `description` (str), `ai_reasoning` (str | None).

### Convenções de migração (Alembic)

O projeto usa Alembic para migrações. Padrão atual: `backend/alembic/versions/004_add_missing_news_indexes.py`. Novo arquivo: `005_add_fts5_search.py`.

```python
# 004_add_missing_news_indexes.py — padrão de migration para seguir
def upgrade() -> None:
    op.create_index("idx_news_folder", "news_items", ["folder_id"])
    ...

def downgrade() -> None:
    op.drop_index("idx_news_folder", table_name="news_items")
    ...
```

Para FTS5, Alembic não tem primitiva nativa — usar `op.execute()` com SQL raw.

## Scope

**In scope**:
- `backend/alembic/versions/005_add_fts5_search.py` — criar
- `backend/app/repositories/news.py` — substituir o bloco ILIKE no `apply_news_filters`
- `backend/app/models.py` — adicionar helper para garantir tabela FTS no startup (opcional, como fallback da migration)

**Out of scope** (não tocar):
- `backend/app/routes/news.py` — interface pública não muda
- Frontend — sem mudanças de frontend; o parâmetro `q` já é enviado pelo FilterBar
- `backend/app/services/` — zero mudanças nos serviços

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run migrations | `cd backend && alembic upgrade head` | `Running upgrade ... -> 005...` |
| Run tests | `cd backend && pytest -q` | all pass |
| Test search | `cd backend && python -c "from app.database import get_engine; from sqlalchemy import text; e = get_engine(); print(e.execute(text(\"SELECT fts5 FROM pragma_compile_options\")).fetchone())"` | — |
| Import check | `cd backend && python -c "from app.repositories.news import list_news_filtered; print('ok')"` | ok |

## Steps

### Step 1: Criar migration FTS5

Criar `backend/alembic/versions/005_add_fts5_search.py`:

```python
"""Add FTS5 virtual table for full-text search

Revision ID: 005
Revises: 004
Create Date: 2026-06-20
"""
from alembic import op

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Tabela virtual FTS5 — indexa title, title_original, description, ai_reasoning
    # content='news_items' + content_rowid='id' mantém sincronia automática via triggers
    op.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS news_fts
        USING fts5(
            title,
            title_original,
            description,
            ai_reasoning,
            content='news_items',
            content_rowid='id'
        )
        """
    )
    # Popula a tabela com dados existentes
    op.execute(
        """
        INSERT INTO news_fts(rowid, title, title_original, description, ai_reasoning)
        SELECT id, title, title_original, description, COALESCE(ai_reasoning, '')
        FROM news_items
        """
    )
    # Triggers para manter FTS sincronizado após INSERT, UPDATE, DELETE
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS news_items_ai
        AFTER INSERT ON news_items BEGIN
            INSERT INTO news_fts(rowid, title, title_original, description, ai_reasoning)
            VALUES (new.id, new.title, new.title_original, new.description, COALESCE(new.ai_reasoning, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS news_items_ad
        AFTER DELETE ON news_items BEGIN
            INSERT INTO news_fts(news_fts, rowid, title, title_original, description, ai_reasoning)
            VALUES ('delete', old.id, old.title, old.title_original, old.description, COALESCE(old.ai_reasoning, ''));
        END
        """
    )
    op.execute(
        """
        CREATE TRIGGER IF NOT EXISTS news_items_au
        AFTER UPDATE ON news_items BEGIN
            INSERT INTO news_fts(news_fts, rowid, title, title_original, description, ai_reasoning)
            VALUES ('delete', old.id, old.title, old.title_original, old.description, COALESCE(old.ai_reasoning, ''));
            INSERT INTO news_fts(rowid, title, title_original, description, ai_reasoning)
            VALUES (new.id, new.title, new.title_original, new.description, COALESCE(new.ai_reasoning, ''));
        END
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS news_items_au")
    op.execute("DROP TRIGGER IF EXISTS news_items_ad")
    op.execute("DROP TRIGGER IF EXISTS news_items_ai")
    op.execute("DROP TABLE IF EXISTS news_fts")
```

**Verify**: `cd backend && alembic upgrade head` → saída mostra `Running upgrade 004 -> 005`

**Verify**: `cd backend && python -c "
from app.database import SessionLocal
from sqlalchemy import text
db = SessionLocal()
result = db.execute(text(\"SELECT count(*) FROM news_fts\")).scalar()
print('FTS rows:', result)
db.close()
"` → imprime `FTS rows: <N>` (N igual ao número de itens em news_items)

### Step 2: Substituir ILIKE por FTS5 em `apply_news_filters`

Em `backend/app/repositories/news.py`, substituir o bloco `if q:` (linhas 70-77) pelo seguinte:

```python
from sqlalchemy import text  # adicionar ao import no topo do arquivo se não existir

if q:
    # FTS5 match — retorna apenas IDs que satisfazem a busca
    fts_query = q.strip().replace('"', '""')  # escapa aspas duplas para FTS5
    fts_ids = [
        row[0]
        for row in db.execute(
            text(
                "SELECT rowid FROM news_fts WHERE news_fts MATCH :q ORDER BY rank"
            ),
            {"q": fts_query},
        ).fetchall()
    ]
    if fts_ids:
        query = query.where(NewsItem.id.in_(fts_ids))
    else:
        # Nenhum resultado FTS — retornar zero resultados
        query = query.where(NewsItem.id.is_(None))
```

**Atenção**: `apply_news_filters` recebe `query` mas também precisa acesso à `db` para executar o SQL FTS. Verifique que `db` é passado como argumento. Se não for, veja abaixo.

**Verificação prévia**: procurar como `db` está disponível em `apply_news_filters`:

```
grep -n "def apply_news_filters\|def list_news_filtered\|def count_news_filtered" backend/app/repositories/news.py
```

O estado atual de `apply_news_filters` NÃO recebe `db` como parâmetro — ela recebe apenas `query` e os filtros. `db` está disponível em `list_news_filtered` e `count_news_filtered`.

**Solução correta**: modificar `apply_news_filters` para aceitar `db` como primeiro parâmetro:

```python
def apply_news_filters(
    query,
    db: Session,
    *,
    is_read: bool | None,
    is_bookmarked: bool | None,
    ai_relevance: str | None,
    folder_id: int | None,
    source: str | None,
    min_hype: int | None,
    hype: int | None,
    obsidian_exported: bool | None,
    q: str | None,
):
    if is_read is not None:
        query = query.where(NewsItem.is_read == is_read)
    if is_bookmarked is not None:
        query = query.where(NewsItem.is_bookmarked == is_bookmarked)
    if ai_relevance is not None:
        query = query.where(NewsItem.ai_relevance == ai_relevance)
    if folder_id is not None:
        if folder_id == -1:
            query = query.where(NewsItem.folder_id.is_(None))
        else:
            query = query.where(NewsItem.folder_id == folder_id)
    if source is not None:
        if source == "rss":
            query = query.where(NewsItem.source.startswith("rss/"))
        else:
            query = query.where(NewsItem.source == source)
    if min_hype is not None:
        query = query.where(NewsItem.hype_score >= min_hype)
    if hype is not None:
        query = query.where(NewsItem.hype_score == hype)
    if obsidian_exported is True:
        query = query.where(NewsItem.obsidian_exported_at.isnot(None))
    elif obsidian_exported is False:
        query = query.where(NewsItem.obsidian_exported_at.is_(None))
    if q:
        fts_query = q.strip().replace('"', '""')
        fts_ids = [
            row[0]
            for row in db.execute(
                text("SELECT rowid FROM news_fts WHERE news_fts MATCH :q ORDER BY rank"),
                {"q": fts_query},
            ).fetchall()
        ]
        if fts_ids:
            query = query.where(NewsItem.id.in_(fts_ids))
        else:
            query = query.where(NewsItem.id.is_(None))
    return query
```

E atualizar os callers para passar `db`:

```python
# count_news_filtered
def count_news_filtered(db: Session, **filters) -> int:
    query = select(func.count()).select_from(NewsItem)
    query = apply_news_filters(query, db, **filters)
    return db.scalar(query) or 0


# list_news_filtered
def list_news_filtered(
    db: Session,
    *,
    limit: int,
    offset: int,
    **filters,
) -> tuple[list[NewsItem], int]:
    base = select(NewsItem).options(joinedload(NewsItem.folder))
    base = apply_news_filters(base, db, **filters)

    count_query = select(func.count()).select_from(NewsItem)
    count_query = apply_news_filters(count_query, db, **filters)
    total = db.scalar(count_query) or 0

    items = db.scalars(
        base.order_by(NewsItem.created_at.desc()).limit(limit).offset(offset)
    ).all()
    return list(items), total
```

**Verify**: `cd backend && python -c "from app.repositories.news import list_news_filtered; print('ok')"` → `ok`

**Verify**: `cd backend && grep -n "def apply_news_filters" backend/app/repositories/news.py` → mostra `db: Session` como segundo parâmetro

### Step 3: Adicionar `text` ao import de SQLAlchemy

No topo de `backend/app/repositories/news.py`, verificar se `text` está importado:

```python
from sqlalchemy import func, or_, select, text
```

Se `text` não estava no import original, adicionar.

### Step 4: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

**Verify**: `cd backend && pytest tests/ -k "search or news" -v` → testes relevantes passam

### Step 5: Teste manual de sanidade

```
cd backend && python -c "
from app.database import SessionLocal
from app.repositories.news import list_news_filtered
db = SessionLocal()
items, total = list_news_filtered(db, limit=5, offset=0, q='python', is_read=None, is_bookmarked=None, ai_relevance=None, folder_id=None, source=None, min_hype=None, hype=None, obsidian_exported=None)
print(f'Found {total} results for q=python')
for item in items[:3]:
    print(f'  [{item.id}] {item.title[:60]}')
db.close()
"
```

→ Imprime resultados sem exceção. Se o banco estiver vazio, `Found 0 results` é aceitável.

## Test plan

Adicionar `backend/tests/test_fts_search.py`:

```python
"""Testes para busca FTS5 em news items."""
import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.repositories.news import count_news_filtered, list_news_filtered


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def test_fts_table_exists(db):
    result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='news_fts'")).fetchone()
    assert result is not None, "Tabela news_fts não existe — rode alembic upgrade head"


def test_search_returns_results_or_empty(db):
    """Busca por termo genérico não deve lançar exceção."""
    items, total = list_news_filtered(
        db, limit=10, offset=0, q="python",
        is_read=None, is_bookmarked=None, ai_relevance=None,
        folder_id=None, source=None, min_hype=None, hype=None,
        obsidian_exported=None,
    )
    assert isinstance(total, int)
    assert total >= 0


def test_search_empty_query_ignored(db):
    """q=None deve retornar todos os itens (sem filtro)."""
    all_items, total_all = list_news_filtered(
        db, limit=100, offset=0, q=None,
        is_read=None, is_bookmarked=None, ai_relevance=None,
        folder_id=None, source=None, min_hype=None, hype=None,
        obsidian_exported=None,
    )
    assert isinstance(total_all, int)


def test_search_no_match_returns_zero(db):
    """Termo inexistente retorna zero resultados."""
    items, total = list_news_filtered(
        db, limit=10, offset=0, q="xyzxyzimpossibleterm9999",
        is_read=None, is_bookmarked=None, ai_relevance=None,
        folder_id=None, source=None, min_hype=None, hype=None,
        obsidian_exported=None,
    )
    assert total == 0
    assert items == []
```

**Verify**: `cd backend && pytest tests/test_fts_search.py -v` → todos passam

## Done criteria

- [ ] `cd backend && alembic upgrade head` → mostra `Running upgrade 004 -> 005`
- [ ] `backend/alembic/versions/005_add_fts5_search.py` existe
- [ ] `grep -n "news_fts" backend/alembic/versions/005_add_fts5_search.py` → 3+ matches (CREATE + triggers)
- [ ] `grep -n "MATCH" backend/app/repositories/news.py` → 1+ match
- [ ] `grep -n "ilike\|ILIKE" backend/app/repositories/news.py` → 0 matches (ILIKE removido)
- [ ] `grep -n "def apply_news_filters" backend/app/repositories/news.py` → assinatura tem `db: Session`
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_fts_search.py -v` → all pass
- [ ] Nenhum arquivo em `backend/app/routes/` foi modificado

## STOP conditions

Pare e reporte se:
- `alembic upgrade head` falhar com erro SQL → verifique `down_revision` do arquivo 005 e se 004 está aplicado (`alembic current`).
- `pytest` reportar erros em `tests/test_news_routes.py` ou `tests/test_repositories.py` — a mudança de assinatura de `apply_news_filters` pode quebrar callers não mapeados. Use `grep -rn "apply_news_filters" backend/` para encontrá-los e atualizá-los antes de reportar.
- `SELECT rowid FROM news_fts WHERE news_fts MATCH` lançar `OperationalError` → FTS5 pode não estar compilado no SQLite disponível. Verifique com `python -c "import sqlite3; conn=sqlite3.connect(':memory:'); conn.execute('CREATE VIRTUAL TABLE t USING fts5(a)')"`.

## Maintenance notes

- **Triggers mantêm FTS sincronizado automaticamente**: todo INSERT/UPDATE/DELETE em `news_items` dispara o trigger. Não é necessário código adicional no ingest.
- **FTS5 não suporta todos os operadores SQL**: `WHERE news_fts MATCH 'python AND rust'` funciona; operadores de prefix `python*` também. Mas `OR` no FTS é diferente do SQL `OR`.
- **Escaping de aspas**: o `replace('"', '""')` trata o caso onde o usuário digita aspas duplas no campo de busca, que são tokens especiais no FTS5.
- **`content=` vs tabela independente**: a opção `content='news_items'` significa que FTS5 não duplica os dados — mantém apenas o índice invertido. Os triggers são obrigatórios para manter o índice atualizado.
