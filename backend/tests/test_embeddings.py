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
