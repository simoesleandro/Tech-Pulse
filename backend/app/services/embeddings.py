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

_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE", "http://localhost:11434")
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

    Performance note: carrega todos os embeddings na memória. Para bancos com
    >50k itens, considerar pré-filtrar por ai_relevance='RELEVANTE' ou usar
    um índice ANN externo (ex: faiss).
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
