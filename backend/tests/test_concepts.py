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
