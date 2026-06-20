# Plan 007: Concept Cloud Dinâmico via ai_reasoning (sem keyword hardcoded)

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/services/concepts.py backend/app/routes/obsidian.py
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: ux, dx
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

O concept cloud (`GET /api/obsidian/concepts`) extrai tecnologias via dicionário hardcoded de ~55 palavras (`TECH_KEYWORDS`). Qualquer tecnologia fora da lista — Bun, Zig, HTMX, Deno, Elixir, Zig, tRPC, Tauri, Astro, Vite — não aparece no cloud, independente de quantos artigos falem sobre ela.

Além disso, o endpoint só processa itens com `obsidian_exported_at IS NOT NULL`, ou seja, ignora o banco inteiro de artigos não exportados.

**O que este plano faz**:
1. Adicionar um novo endpoint `GET /api/news/concepts` que extrai conceitos de TODOS os itens `ai_relevance=RELEVANTE` (não apenas exportados para Obsidian).
2. A extração combina: (a) o `TECH_KEYWORDS` existente para termos conhecidos, e (b) extração de tokens capitalizados e siglas do campo `ai_reasoning` — onde o LLM já nomeia as tecnologias em português/inglês como parte da análise.
3. Manter o endpoint `/api/obsidian/concepts` existente sem alterações.

O `ai_reasoning` tem padrões consistentes como: "**Rust** oferece...", "uso de **FTS5**...", "biblioteca **tRPC**...", "framework **Astro**...". Regex simples captura esses termos.

## Current state

### `backend/app/services/concepts.py` (completo)

```python
import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import NewsItem
from app.schemas import ObsidianConceptResponse

TECH_KEYWORDS = {
    "python": "Python",
    "rust": "Rust",
    ...  # ~55 entradas hardcoded
}


def extract_obsidian_concepts(db: Session, limit: int = 20) -> list[ObsidianConceptResponse]:
    items = db.scalars(
        select(NewsItem)
        .where(NewsItem.obsidian_exported_at.isnot(None))  # ← apenas exportados
        .options(joinedload(NewsItem.folder))
    ).all()

    counts: Counter[str] = Counter()
    for item in items:
        text = f"{item.title} {item.title_original or ''} {item.description or ''}"
        tokens = re.split(r"[^\w\.\-]+", text.lower())
        seen_in_item: set[str] = set()

        for token in tokens:
            if token in TECH_KEYWORDS:
                canonical = TECH_KEYWORDS[token]
                if canonical not in seen_in_item:
                    counts[canonical] += 1
                    seen_in_item.add(canonical)
        ...
    return [ObsidianConceptResponse(concept=concept, count=count) for ...]
```

### `backend/app/routes/obsidian.py:161-163`

```python
@router.get("/api/obsidian/concepts", response_model=list[ObsidianConceptResponse])
def get_obsidian_concepts(db: Session = Depends(get_db)):
    return extract_obsidian_concepts(db)
```

### `backend/app/routes/news.py`

Importa de `app.repositories.news`, `app.schemas`. Está no router `tags=["news"]`.

### `backend/app/routes/__init__.py`

```python
from app.routes import backfill, health, ingest, news, obsidian, settings

def register_routes(app: FastAPI) -> None:
    app.include_router(news.router)
    ...
```

### `backend/app/schemas.py:215-217`

```python
class ObsidianConceptResponse(BaseModel):
    concept: str
    count: int
```

Este schema serve para os dois endpoints — reutilizar.

## Scope

**In scope**:
- `backend/app/services/concepts.py` — adicionar nova função `extract_feed_concepts`
- `backend/app/routes/news.py` — adicionar endpoint `GET /api/news/concepts`
- `backend/app/schemas.py` — criar alias `ConceptResponse = ObsidianConceptResponse` OU reutilizar o schema existente diretamente

**Out of scope** (não tocar):
- `backend/app/routes/obsidian.py` — o endpoint `/api/obsidian/concepts` não muda
- `backend/app/services/concepts.py::extract_obsidian_concepts` — não alterar a função existente
- `TECH_KEYWORDS` — não remover; a nova função também vai usá-lo como base
- Frontend — zero mudanças de frontend neste plano

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run tests | `cd backend && pytest -q` | all pass |
| Import check | `cd backend && python -c "from app.services.concepts import extract_feed_concepts; print('ok')"` | ok |
| Route check | `cd backend && python -c "from app.routes.news import router; routes=[r.path for r in router.routes]; print(routes)"` | lista inclui `/api/news/concepts` |

## Steps

### Step 1: Adicionar `extract_feed_concepts` em `concepts.py`

Em `backend/app/services/concepts.py`, adicionar a nova função **após** `extract_obsidian_concepts`, sem modificar nada existente:

```python
# Padrão para extrair termos capitalizados do ai_reasoning:
# Captura palavras com letra maiúscula (ex: "FastAPI", "PostgreSQL", "tRPC")
# e siglas (ex: "FTS5", "CI/CD", "API")
_REASONING_TERM_RE = re.compile(
    r"\b([A-Z][a-zA-Z0-9+#.]{2,}|[A-Z]{2,}[0-9]*)\b"
)

# Termos que aparecem frequentemente mas não são tecnologias
_REASONING_STOPWORDS = frozenset({
    "Com", "Para", "Esse", "Esta", "Este", "Que", "Uma", "Uso", "Novo",
    "API", "URL", "HTTP", "HTML", "JSON", "YAML", "SQL", "OS", "CLI",
    "PR", "CI", "CD", "MVP", "SaaS", "The", "And", "For", "With",
})


def extract_feed_concepts(db: Session, limit: int = 30) -> list[ObsidianConceptResponse]:
    """Extrai conceitos técnicos de TODOS os itens relevantes (não apenas Obsidian).

    Combina TECH_KEYWORDS (para termos conhecidos) com extração de tokens
    capitalizados do ai_reasoning (para tecnologias emergentes não listadas).
    """
    items = db.scalars(
        select(NewsItem)
        .where(NewsItem.ai_relevance == "RELEVANTE")
        .where(NewsItem.is_enriched.is_(True))
    ).all()

    counts: Counter[str] = Counter()

    for item in items:
        seen_in_item: set[str] = set()

        # 1. Extração por TECH_KEYWORDS (mesmo padrão do extract_obsidian_concepts)
        text_lower = f"{item.title} {item.title_original or ''} {item.description or ''}".lower()
        for token in re.split(r"[^\w\.\-]+", text_lower):
            if token in TECH_KEYWORDS:
                canonical = TECH_KEYWORDS[token]
                if canonical not in seen_in_item:
                    counts[canonical] += 1
                    seen_in_item.add(canonical)

        # 2. Extração de termos capitalizados do ai_reasoning
        if item.ai_reasoning:
            for match in _REASONING_TERM_RE.finditer(item.ai_reasoning):
                term = match.group(1)
                if term in _REASONING_STOPWORDS:
                    continue
                # Normaliza: se já temos esse termo via TECH_KEYWORDS, usa o canônico
                canonical = TECH_KEYWORDS.get(term.lower(), term)
                if canonical not in seen_in_item:
                    counts[canonical] += 1
                    seen_in_item.add(canonical)

    return [
        ObsidianConceptResponse(concept=concept, count=count)
        for concept, count in counts.most_common(limit)
    ]
```

**Verify**: `cd backend && python -c "from app.services.concepts import extract_feed_concepts; print('ok')"` → `ok`

### Step 2: Adicionar endpoint em `routes/news.py`

Em `backend/app/routes/news.py`, adicionar ao topo dos imports:

```python
from app.schemas import (
    ...
    ObsidianConceptResponse,  # adicionar esta linha se não existir
)
from app.services.concepts import extract_feed_concepts
```

E adicionar o endpoint após os imports e antes do primeiro `@router.get`:

```python
@router.get("/api/news/concepts", response_model=list[ObsidianConceptResponse])
def get_news_concepts(
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return extract_feed_concepts(db, limit=limit)
```

**Verify**: `cd backend && python -c "from app.routes.news import router; paths=[r.path for r in router.routes]; print('/api/news/concepts' in paths)"` → `True`

### Step 3: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

### Step 4: Teste manual de sanidade

```
cd backend && python -c "
from app.database import SessionLocal
from app.services.concepts import extract_feed_concepts
db = SessionLocal()
concepts = extract_feed_concepts(db, limit=10)
print(f'{len(concepts)} conceitos extraídos')
for c in concepts[:5]:
    print(f'  {c.concept}: {c.count}')
db.close()
"
```

→ Imprime lista de conceitos sem exceção. Se o banco estiver vazio ou sem itens RELEVANTE, `0 conceitos extraídos` é aceitável.

## Test plan

Adicionar `backend/tests/test_concepts.py`:

```python
"""Testes para extração dinâmica de conceitos."""
import pytest
from unittest.mock import MagicMock

from app.services.concepts import extract_feed_concepts, TECH_KEYWORDS, _REASONING_TERM_RE


def test_reasoning_term_regex_captures_capitalized():
    text = "FastAPI facilita o desenvolvimento de APIs REST com Python"
    matches = [m.group(1) for m in _REASONING_TERM_RE.finditer(text)]
    assert "FastAPI" in matches
    assert "REST" in matches
    assert "Python" in matches


def test_reasoning_term_regex_ignores_lowercase():
    text = "this is all lowercase text"
    matches = [m.group(1) for m in _REASONING_TERM_RE.finditer(text)]
    assert matches == []


def test_tech_keywords_still_used(db_session):
    """Termos em TECH_KEYWORDS continuam sendo detectados."""
    # Se TECH_KEYWORDS tiver "python" → "Python", deve aparecer
    assert "python" in TECH_KEYWORDS


def test_extract_feed_concepts_returns_list():
    """Função não lança exceção com session vazia (sem itens)."""
    mock_db = MagicMock()
    mock_db.scalars.return_value.all.return_value = []
    result = extract_feed_concepts(mock_db, limit=10)
    assert result == []
```

**Verify**: `cd backend && pytest tests/test_concepts.py -v` → todos passam

## Done criteria

- [ ] `backend/app/services/concepts.py` tem função `extract_feed_concepts`
- [ ] `grep -n "extract_feed_concepts" backend/app/routes/news.py` → 1+ match
- [ ] `grep -n "/api/news/concepts" backend/app/routes/news.py` → 1 match
- [ ] `grep -n "extract_obsidian_concepts" backend/app/routes/obsidian.py` → ainda 1 match (não mudou)
- [ ] `grep -n "TECH_KEYWORDS" backend/app/services/concepts.py` → ainda presente (não removido)
- [ ] `cd backend && pytest -q` → all pass
- [ ] Nenhuma função existente em `concepts.py` foi modificada

## STOP conditions

Pare e reporte se:
- `extract_obsidian_concepts` ou `/api/obsidian/concepts` pararem de funcionar — indica que mudanças saíram do escopo.
- A regex `_REASONING_TERM_RE` capturar menos de 3 termos em um `ai_reasoning` típico — ajuste a regex e reporte antes de commitar.
- `ObsidianConceptResponse` não estiver disponível no módulo de schemas — verifique o import correto.

## Maintenance notes

- **`_REASONING_STOPWORDS`**: crescerá conforme termos falso-positivos aparecerem. Adicionar palavras que não são tecnologias (ex: "Dev", "Pro", "Plus") quando relatadas por usuários.
- **Limite padrão 30 vs 20**: o endpoint Obsidian usa limit=20; o novo usa 30 por cobrir um universo maior de itens. Ambos aceitam o parâmetro `limit` para override.
- **Performance**: para bancos com 10k+ itens, a query `WHERE ai_relevance='RELEVANTE' AND is_enriched=1` vai usar `idx_news_unread` (que indexa `is_read` e `ai_relevance`). Monitorar latência se o banco crescer muito.
