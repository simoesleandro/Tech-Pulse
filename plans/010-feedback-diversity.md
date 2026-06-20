# Plan 010: Feedback Diversificado — TALVEZ + Cache por Fonte + Histórico

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/routes/news.py backend/app/services/ai_agent.py
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P2
- **Effort**: S
- **Risk**: LOW
- **Depends on**: none
- **Category**: ux, feature
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

O sistema de feedback atual tem três problemas:

1. **Binário demais**: só aceita `RELEVANTE | LIXO`. Não existe "talvez" ou "interessante mas não urgente". O LLM recebe apenas dois extremos como exemplos — sem calibrar o threshold médio.

2. **Few-shot sem diversidade**: `update_feedback_cache` guarda os últimos 20 exemplos cronologicamente. Se o usuário der feedback só em artigos do Reddit por 3 dias, os 20 exemplos serão todos de Reddit. O LLM não aprende sobre Dev.to ou GitHub Trends.

3. **Sem histórico visível**: não existe endpoint para o usuário ver ou corrigir feedback dado. Para corrigir um erro (ex: marcou LIXO por engano), o usuário precisa dar o feedback oposto — mas não sabe o que marcou antes.

**O que este plano faz**:
1. Adicionar `TALVEZ` como terceiro valor de `user_relevance` — representa "não sei" ou "leia depois".
2. Modificar `update_feedback_cache` para garantir diversidade por fonte: no máximo 4 exemplos por source.
3. Adicionar `GET /api/feedback` que retorna os últimos N feedbacks dados pelo usuário.

## Current state

### `backend/app/routes/news.py:195-224` — endpoint de feedback atual

```python
@router.patch("/api/news/{item_id}/relevance", response_model=NewsItemResponse, dependencies=[Depends(require_api_key)])
def update_relevance_feedback(
    item_id: int,
    relevance: str = Query(pattern="^(RELEVANTE|LIXO)$"),  # ← só 2 valores
    db: Session = Depends(get_db),
):
    """User feedback — overrides ai_relevance and updates the few-shot cache."""
    db_item = db.get(NewsItem, item_id)
    if db_item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    db_item.user_relevance = relevance
    db_item.ai_relevance = relevance  # ← sobrescreve ai_relevance também
    db.commit()

    from app.services.ai_agent import update_feedback_cache
    examples = [
        {"title": i.title_original, "source": i.source, "verdict": i.user_relevance}
        for i in db.scalars(
            select(NewsItem)
            .where(NewsItem.user_relevance.isnot(None))
            .order_by(NewsItem.created_at.desc())
            .limit(20)        # ← últimos 20, sem diversidade
        ).all()
    ]
    update_feedback_cache(examples)
    ...
```

### `backend/app/services/ai_agent.py` — cache de feedback (pós plano 004)

```python
_feedback_lock = threading.Lock()
_feedback_examples: list[dict] = []


def update_feedback_cache(examples: list[dict]) -> None:
    global _feedback_examples
    with _feedback_lock:
        _feedback_examples = list(examples[-20:])   # ← últimos 20 cronológicos


def _format_feedback_shots() -> str:
    with _feedback_lock:
        examples = list(_feedback_examples)
    if not examples:
        return ""
    lines = ["Calibração com feedback do usuário (priorize esses padrões):"]
    for ex in examples[-8:]:
        lines.append(f"  [{ex['verdict']}] \"{ex['title'][:80]}\" (fonte: {ex['source']})")
    return "\n".join(lines) + "\n\n"
```

### `backend/app/models.py:49` — campo `user_relevance`

```python
user_relevance: Mapped[str | None] = mapped_column(String, nullable=True)
```

Sem constraint de valor — qualquer string é aceita no banco. A constraint está na rota (`pattern="^(RELEVANTE|LIXO)$"`).

### `backend/app/schemas.py:26` — `NewsItemResponse`

```python
user_relevance: str | None = None
```

Já presente no response schema. `TALVEZ` será retornado como string, sem mudanças no schema.

## Scope

**In scope**:
- `backend/app/routes/news.py` — modificar pattern de `relevance` para incluir `TALVEZ`; modificar query de exemplos para diversidade; adicionar `GET /api/feedback`
- `backend/app/services/ai_agent.py` — modificar `update_feedback_cache` para receber lista diversificada (a lógica de diversidade fica na rota, não no cache)

**Out of scope** (não tocar):
- `backend/app/models.py` — o campo `user_relevance` já é String sem constraint; sem mudanças
- Migrations Alembic — sem novas colunas neste plano
- Frontend — sem mudanças de UI neste plano

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Run tests | `cd backend && pytest -q` | all pass |
| Import check | `cd backend && python -c "from app.routes.news import router; print('ok')"` | ok |
| Route check | `cd backend && python -c "from app.routes.news import router; paths=[r.path for r in router.routes]; print('/api/feedback' in paths)"` | True |

## Steps

### Step 1: Ampliar o pattern de `relevance` para incluir `TALVEZ`

Em `backend/app/routes/news.py`, na função `update_relevance_feedback` (linha ~198), alterar:

```python
# ANTES:
relevance: str = Query(pattern="^(RELEVANTE|LIXO)$"),

# DEPOIS:
relevance: str = Query(pattern="^(RELEVANTE|LIXO|TALVEZ)$"),
```

### Step 2: Modificar a lógica de `ai_relevance` para respeitar `TALVEZ`

Na mesma função, a linha `db_item.ai_relevance = relevance` sobrescreve a classificação do LLM. Para `TALVEZ`, queremos manter o `ai_relevance` original (não sobrescrever com "TALVEZ" que o sistema não entende como filtro):

```python
db_item.user_relevance = relevance
# TALVEZ não sobrescreve ai_relevance — mantém a classificação do LLM intacta
if relevance in ("RELEVANTE", "LIXO"):
    db_item.ai_relevance = relevance
db.commit()
```

### Step 3: Substituir query de exemplos por versão com diversidade por fonte

Ainda em `update_relevance_feedback`, substituir o bloco de `examples` por:

```python
from app.services.ai_agent import update_feedback_cache

# Coleta até 4 exemplos por source para garantir diversidade no few-shot
# Exclui TALVEZ do few-shot — só RELEVANTE e LIXO calibram o LLM
raw_examples = db.scalars(
    select(NewsItem)
    .where(NewsItem.user_relevance.in_(["RELEVANTE", "LIXO"]))
    .order_by(NewsItem.created_at.desc())
    .limit(100)  # pool grande para selecionar com diversidade
).all()

# Garante no máximo 4 exemplos por fonte
source_counts: dict[str, int] = {}
diverse_examples: list[dict] = []
for i in raw_examples:
    src = i.source
    if source_counts.get(src, 0) < 4:
        diverse_examples.append(
            {"title": i.title_original, "source": src, "verdict": i.user_relevance}
        )
        source_counts[src] = source_counts.get(src, 0) + 1
    if len(diverse_examples) >= 20:
        break

update_feedback_cache(diverse_examples)
```

**Verify**: `cd backend && python -c "from app.routes.news import update_relevance_feedback; print('ok')"` → `ok`

### Step 4: Adicionar endpoint `GET /api/feedback`

Em `backend/app/routes/news.py`, adicionar antes do último endpoint:

```python
class FeedbackItemResponse(BaseModel):
    id: int
    title: str
    title_original: str
    source: str
    user_relevance: str
    ai_relevance: str
    created_at: datetime


@router.get("/api/feedback", response_model=list[FeedbackItemResponse], dependencies=[Depends(require_api_key)])
def list_feedback(
    limit: int = Query(default=50, ge=1, le=200),
    verdict: str | None = Query(default=None, pattern="^(RELEVANTE|LIXO|TALVEZ)$"),
    db: Session = Depends(get_db),
):
    """Retorna os feedbacks dados pelo usuário, para revisão e auditoria."""
    query = select(NewsItem).where(NewsItem.user_relevance.isnot(None))
    if verdict is not None:
        query = query.where(NewsItem.user_relevance == verdict)
    items = db.scalars(
        query.order_by(NewsItem.created_at.desc()).limit(limit)
    ).all()
    return [
        FeedbackItemResponse(
            id=item.id,
            title=item.title,
            title_original=item.title_original,
            source=item.source,
            user_relevance=item.user_relevance,
            ai_relevance=item.ai_relevance,
            created_at=item.created_at,
        )
        for item in items
    ]
```

Adicionar `FeedbackItemResponse` ao topo de `routes/news.py` ou dentro da função como classe local. Prefira definir no mesmo arquivo (não em `schemas.py`) para manter o escopo.

Verificar que `datetime` está importado em `routes/news.py`. Se não estiver:

```python
from datetime import datetime
```

Adicionar `BaseModel` ao import de pydantic se necessário:

```python
from pydantic import BaseModel
```

**Verify**: `cd backend && python -c "
from app.routes.news import router
paths = [r.path for r in router.routes]
print('/api/feedback' in paths)
"` → `True`

### Step 5: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

## Test plan

Adicionar `backend/tests/test_feedback_diversity.py`:

```python
"""Testes para o sistema de feedback diversificado."""
import pytest
from app.services.ai_agent import update_feedback_cache, _format_feedback_shots


def test_update_feedback_cache_diverse():
    """Cache aceita lista com múltiplas fontes."""
    examples = [
        {"title": "Python guide", "source": "dev.to", "verdict": "RELEVANTE"},
        {"title": "Rust book", "source": "reddit", "verdict": "LIXO"},
        {"title": "Go tutorial", "source": "hacker_news", "verdict": "RELEVANTE"},
    ]
    update_feedback_cache(examples)
    shots = _format_feedback_shots()
    assert "RELEVANTE" in shots
    assert "LIXO" in shots


def test_format_feedback_shots_empty():
    """Sem exemplos, retorna string vazia."""
    update_feedback_cache([])
    assert _format_feedback_shots() == ""


def test_update_feedback_cache_truncates_at_20():
    """Cache mantém no máximo 20 exemplos."""
    examples = [
        {"title": f"Article {i}", "source": "dev.to", "verdict": "RELEVANTE"}
        for i in range(30)
    ]
    update_feedback_cache(examples)
    import app.services.ai_agent as m
    import threading
    with m._feedback_lock:
        assert len(m._feedback_examples) <= 20


def test_talvez_not_in_format_feedback_shots():
    """TALVEZ não deve aparecer nos few-shot (foi filtrado na rota)."""
    examples = [
        {"title": "Something", "source": "dev.to", "verdict": "RELEVANTE"},
    ]
    update_feedback_cache(examples)
    shots = _format_feedback_shots()
    assert "TALVEZ" not in shots
```

**Verify**: `cd backend && pytest tests/test_feedback_diversity.py -v` → todos passam

## Done criteria

- [ ] `grep -n "TALVEZ" backend/app/routes/news.py` → 2+ matches (pattern + lógica de ai_relevance)
- [ ] `grep -n "source_counts" backend/app/routes/news.py` → 1+ match (diversidade por fonte)
- [ ] `grep -n "/api/feedback" backend/app/routes/news.py` → 1 match
- [ ] `grep -n "FeedbackItemResponse" backend/app/routes/news.py` → 1+ match
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_feedback_diversity.py -v` → all pass
- [ ] `grep -n "ai_relevance = relevance" backend/app/routes/news.py` → dentro de `if relevance in ("RELEVANTE", "LIXO"):` (não incondicional)

## STOP conditions

Pare e reporte se:
- `_format_feedback_shots` começar a incluir `TALVEZ` nos exemplos — indica que a filtragem `in_(["RELEVANTE", "LIXO"])` não está funcionando. Debug antes de commitar.
- Os testes existentes em `test_ai_agent.py` ou `test_app_config.py` falharem após as mudanças — a interface de `update_feedback_cache` não pode mudar de tipo.
- O pattern `^(RELEVANTE|LIXO|TALVEZ)$` for rejeitado pelo FastAPI (improvável) — verifique a versão do Pydantic.

## Maintenance notes

- **`TALVEZ` e filtros da UI**: o campo `ai_relevance` não recebe `TALVEZ` (pela lógica do Step 2). Isso preserva os filtros da UI que filtram por `ai_relevance=RELEVANTE` — artigos marcados como TALVEZ ainda aparecem no feed normal. O `user_relevance=TALVEZ` é apenas informativo.
- **Diversidade por source**: `source_counts.get(src, 0) < 4` significa no máximo 4 por fonte. Com 5 fontes (dev.to, reddit, github_trends, hacker_news, rss/*), o cache pode ter até 20 exemplos totais (4 × 5). Se o usuário só usa dev.to, o limite prático será 4.
- **Futuro**: quando o front-end tiver uma tela de "Histórico de Feedback", usar `GET /api/feedback?verdict=LIXO` para permitir ao usuário revisar e corrigir feedbacks errados (via PATCH existente).
