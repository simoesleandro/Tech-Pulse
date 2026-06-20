# Plan 013: Semantic Search via Ollama Embeddings + Cosine Similarity

> **Executor instructions**: Follow this plan step by step. Run every
> verification command and confirm the expected result before moving to the
> next step. If anything in the "STOP conditions" section occurs, stop and
> report — do not improvise. When done, update the status row for this plan
> in `plans/README.md`.
>
> **Drift check (run first)**:
> ```
> git diff --stat 61a5610..HEAD -- backend/app/models.py backend/app/services/ai_agent.py backend/alembic/versions/
> ```
> Se qualquer arquivo mudou, compare antes de prosseguir.

## Status

- **Priority**: P3
- **Effort**: L
- **Risk**: MEDIUM
- **Depends on**: none (mas interaje com modelos Ollama — requer Ollama rodando)
- **Category**: feature
- **Planned at**: commit `61a5610`, 2026-06-20

## Why this matters

A busca textual (`q=` ILIKE ou FTS5 do plano 006) exige que o usuário lembre a palavra exata. Busca semântica resolve: "encontre artigos similares a este sobre compiladores" ou "quero artigos que falem de performance mas com outro vocabulário".

Ollama já está integrado (`app/services/ai_agent.py` usa `requests.post` para `OLLAMA_BASE_URL`). O endpoint `/api/embeddings` do Ollama gera vetores que podem ser persistidos no SQLite como BLOB e comparados com cosine similarity.

Casos de uso:
- `GET /api/news/{id}/similar` — artigos similares a um dado
- `POST /api/news/search/semantic?q=texto` — busca semântica por texto livre

## Current state

### `backend/app/services/ai_agent.py` — integração Ollama existente

```python
# Verificar como OLLAMA_BASE_URL é configurado:
grep -n "OLLAMA_BASE_URL\|ollama\|requests.post" backend/app/services/ai_agent.py | head -20
```

Executar antes de prosseguir para ver a URL base e padrão de chamada.

### `backend/app/models.py:21-63` — `NewsItem` atual

Não tem coluna para embedding. Adicionar `embedding: Mapped[bytes | None]` (BLOB em SQLite).

### Ollama embeddings API

```
POST /api/embeddings
{
  "model": "nomic-embed-text",  # ou o modelo disponível
  "prompt": "texto para embedar"
}
→ {"embedding": [0.1, 0.2, ...]}  # vetor de floats
```

O modelo `nomic-embed-text` é leve (~270MB), especializado em embeddings. Alternativa: usar o mesmo modelo do triador (ex: `gemma4:12b`), mas é mais lento e maior para embeddings.

### `backend/requirements.txt`

`numpy` não está listado. Será necessário para serializar/deserializar embeddings como BLOB (`numpy.frombuffer`).

## Scope

**In scope**:
- `backend/requirements.txt` — adicionar `numpy`
- `backend/app/models.py` — adicionar campo `embedding: Mapped[bytes | None]`
- `backend/alembic/versions/007_add_embedding_column.py` (ou número correto — verificar `alembic current`)
- `backend/app/services/embeddings.py` — criar: `get_embedding()`, `embed_item()`, `find_similar()`
- `backend/app/routes/news.py` — adicionar `GET /api/news/{id}/similar`
- `backend/app/routes/ingest.py` — adicionar chamada a `embed_item` após salvar item (ou criar worker separado)

**Out of scope** (não tocar):
- `POST /api/news/search/semantic` — deixar para iteração futura; comece com `GET /api/news/{id}/similar`
- Modelos de embedding externos (OpenAI, Cohere) — apenas Ollama local
- Frontend — zero mudanças de UI neste plano

## Commands you will need

| Purpose | Command | Expected on success |
|---------|---------|---------------------|
| Check Ollama | `curl http://localhost:11434/api/embeddings -d '{"model":"nomic-embed-text","prompt":"test"}' -s \| python -m json.tool \| head -5` | JSON com campo "embedding" |
| Check numpy | `cd backend && python -c "import numpy; print(numpy.__version__)"` | versão |
| Run migrations | `cd backend && alembic upgrade head` | ok |
| Run tests | `cd backend && pytest -q` | all pass |

## Steps

### Step 0: Verificar integração Ollama e modelo de embedding disponível

```
grep -n "OLLAMA_BASE_URL\|OLLAMA_MODEL\|ollama" backend/app/services/ai_agent.py | head -15
```

Anotar: URL base (ex: `http://localhost:11434`), como a URL é construída, se usa `requests` ou `httpx`.

```
curl http://localhost:11434/api/tags -s | python -m json.tool | grep "name"
```

Anotar: quais modelos estão disponíveis. Se `nomic-embed-text` não estiver listado, use `ollama pull nomic-embed-text` ou verifique se o modelo atual suporta embeddings.

### Step 1: Adicionar numpy ao `requirements.txt`

Em `backend/requirements.txt`, adicionar ao final:

```
numpy
```

**Verify**: `cd backend && pip install numpy && python -c "import numpy; print('ok')"` → `ok`

### Step 2: Adicionar coluna `embedding` ao modelo

Em `backend/app/models.py`, adicionar ao `NewsItem`:

```python
from sqlalchemy import LargeBinary  # adicionar ao import existente

class NewsItem(Base):
    ...
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
```

Verificar que `LargeBinary` está no import de `sqlalchemy`.

**Verify**: `cd backend && python -c "from app.models import NewsItem; print(hasattr(NewsItem, 'embedding'))"` → `True`

### Step 3: Criar migration Alembic

Verificar número correto com `cd backend && alembic current`. Usar o próximo número disponível.

```python
"""Add embedding column to news_items

Revision ID: 007  # ajustar conforme alembic current
Revises: 006      # ajustar
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"  # VERIFICAR com alembic current
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_items",
        sa.Column("embedding", sa.LargeBinary, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("news_items", "embedding")
```

**Verify**: `cd backend && alembic upgrade head` → ok

### Step 4: Criar `backend/app/services/embeddings.py`

```python
"""Geração e busca de embeddings semânticos via Ollama."""
import logging
import os
import struct

import numpy as np
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import NewsItem

logger = logging.getLogger(__name__)

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")


def get_embedding(text: str) -> list[float] | None:
    """Gera embedding via Ollama. Retorna None se Ollama não estiver disponível."""
    try:
        response = requests.post(
            f"{_OLLAMA_BASE_URL}/api/embeddings",
            json={"model": _EMBEDDING_MODEL, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json().get("embedding")
    except Exception as exc:
        logger.warning("Embedding generation failed: %s", exc)
        return None


def _to_bytes(vector: list[float]) -> bytes:
    """Serializa lista de floats como bytes (little-endian float32)."""
    return struct.pack(f"{len(vector)}f", *vector)


def _from_bytes(data: bytes) -> np.ndarray:
    """Deserializa bytes como array numpy float32."""
    n = len(data) // 4
    return np.frombuffer(data, dtype=np.float32)


def embed_item(db: Session, item: NewsItem) -> bool:
    """Gera e persiste o embedding para um item. Retorna True se gerado."""
    if item.embedding is not None:
        return False  # já tem embedding

    text = f"{item.title_original}. {item.description or ''}"[:1000]
    vector = get_embedding(text)
    if vector is None:
        return False

    item.embedding = _to_bytes(vector)
    db.commit()
    return True


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def find_similar(
    db: Session,
    item_id: int,
    *,
    limit: int = 10,
    min_similarity: float = 0.7,
) -> list[tuple[NewsItem, float]]:
    """Retorna itens similares ao item_id, ordenados por similaridade coseno.

    Retorna lista vazia se o item não tiver embedding ou Ollama não estiver
    disponível.
    """
    target = db.get(NewsItem, item_id)
    if target is None or target.embedding is None:
        return []

    target_vec = _from_bytes(target.embedding)

    # Carrega todos os itens com embedding — em bancos grandes (>50k),
    # substituir por ANN (Approximate Nearest Neighbor) ou filtro prévio.
    candidates = db.scalars(
        select(NewsItem)
        .where(NewsItem.embedding.isnot(None))
        .where(NewsItem.id != item_id)
    ).all()

    results: list[tuple[NewsItem, float]] = []
    for candidate in candidates:
        try:
            vec = _from_bytes(candidate.embedding)
            sim = _cosine_similarity(target_vec, vec)
            if sim >= min_similarity:
                results.append((candidate, sim))
        except Exception:
            continue

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:limit]
```

**Verify**: `cd backend && python -c "from app.services.embeddings import get_embedding, find_similar, embed_item; print('ok')"` → `ok`

### Step 5: Adicionar endpoint `GET /api/news/{id}/similar`

Em `backend/app/routes/news.py`, adicionar import e endpoint:

```python
from app.services.embeddings import embed_item, find_similar
```

```python
class SimilarNewsResponse(BaseModel):
    item: NewsItemResponse
    similarity: float


@router.get("/api/news/{item_id}/similar", response_model=list[SimilarNewsResponse])
def get_similar_news(
    item_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    min_similarity: float = Query(default=0.7, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """Retorna artigos semanticamente similares. Requer Ollama rodando."""
    item = db.get(NewsItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    # Gera embedding se ainda não tiver (lazy generation)
    if item.embedding is None:
        embed_item(db, item)

    results = find_similar(db, item_id, limit=limit, min_similarity=min_similarity)
    return [
        SimilarNewsResponse(item=news_to_response(candidate), similarity=sim)
        for candidate, sim in results
    ]
```

**Verify**: `cd backend && python -c "
from app.routes.news import router
paths = [r.path for r in router.routes]
print('/api/news/{item_id}/similar' in paths)
"` → `True`

### Step 6: Rodar testes

**Verify**: `cd backend && pytest -q` → all pass

## Test plan

Adicionar `backend/tests/test_embeddings.py`:

```python
"""Testes para o módulo de embeddings semânticos."""
import struct
import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from app.services.embeddings import (
    _to_bytes, _from_bytes, _cosine_similarity, find_similar
)


def test_roundtrip_serialization():
    """Serializar e deserializar preserva os valores."""
    vector = [0.1, 0.2, 0.3, 0.4]
    data = _to_bytes(vector)
    result = _from_bytes(data)
    assert len(result) == 4
    assert abs(result[0] - 0.1) < 1e-6


def test_cosine_similarity_identical():
    """Vetores idênticos têm similaridade 1.0."""
    v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    assert abs(_cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal():
    """Vetores ortogonais têm similaridade 0.0."""
    v1 = np.array([1.0, 0.0], dtype=np.float32)
    v2 = np.array([0.0, 1.0], dtype=np.float32)
    assert abs(_cosine_similarity(v1, v2)) < 1e-6


def test_cosine_similarity_zero_vector():
    """Vetor zero retorna 0.0 sem exceção."""
    v = np.array([0.0, 0.0], dtype=np.float32)
    assert _cosine_similarity(v, v) == 0.0


def test_find_similar_returns_empty_if_no_embedding():
    """find_similar retorna lista vazia se item não tiver embedding."""
    mock_db = MagicMock()
    mock_item = MagicMock()
    mock_item.embedding = None
    mock_db.get.return_value = mock_item
    result = find_similar(mock_db, 1)
    assert result == []


def test_get_embedding_returns_none_on_error():
    """get_embedding retorna None se Ollama não estiver disponível."""
    from app.services.embeddings import get_embedding
    with patch("requests.post", side_effect=Exception("Connection refused")):
        result = get_embedding("test text")
    assert result is None
```

**Verify**: `cd backend && pytest tests/test_embeddings.py -v` → todos passam

## Done criteria

- [ ] `grep -n "numpy" backend/requirements.txt` → 1 match
- [ ] `grep -n "embedding" backend/app/models.py` → 1+ match
- [ ] Migration com `embedding` coluna existe em `backend/alembic/versions/`
- [ ] `cd backend && alembic upgrade head` → ok
- [ ] `backend/app/services/embeddings.py` existe com `get_embedding`, `embed_item`, `find_similar`
- [ ] `grep -n "/similar" backend/app/routes/news.py` → 1 match
- [ ] `cd backend && pytest -q` → all pass
- [ ] `cd backend && pytest tests/test_embeddings.py -v` → all pass

## STOP conditions

Pare e reporte se:
- `alembic upgrade head` falhar por conflito de `down_revision` — verificar `alembic current` e ajustar.
- `nomic-embed-text` não disponível no Ollama local — o endpoint retornará `None` para todos os embeddings. Verifique com `curl http://localhost:11434/api/tags`. Ajuste `_EMBEDDING_MODEL` para um modelo disponível ou documente o `ollama pull nomic-embed-text` como pré-requisito.
- `numpy` não instalar por conflito de versão — reporte o conflito exato. Não tente resolver; aguarde instrução.
- `_from_bytes` retornar array com tamanho errado após roundtrip — indica bug na serialização. Debug `test_roundtrip_serialization` antes de continuar.

## Maintenance notes

- **Performance de `find_similar`**: carrega todos os embeddings na memória. Para bancos com >50k itens, considerar pré-filtrar por `ai_relevance='RELEVANTE'` ou usar um índice ANN externo (ex: `faiss`). Documentar o limite esperado no docstring.
- **Lazy vs eager embedding**: este plano usa lazy (gera no momento da busca). Para embed_all, criar um endpoint `POST /api/embeddings/backfill` que itera todos os itens sem embedding.
- **Modelo**: `nomic-embed-text` produz vetores de 768 dimensões. Mudar o modelo muda o tamanho do vetor — todos os embeddings existentes ficam incompatíveis. Se mudar, fazer backfill completo.
- **Custo de armazenamento**: 768 floats × 4 bytes = ~3KB por item. 10k itens = ~30MB de BLOBs no SQLite. Aceitável.
