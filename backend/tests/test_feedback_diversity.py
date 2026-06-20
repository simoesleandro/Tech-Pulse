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
    assert len(m._feedback_examples) <= 20


def test_talvez_not_in_format_feedback_shots():
    """TALVEZ não deve aparecer nos few-shot (foi filtrado na rota)."""
    examples = [
        {"title": "Something", "source": "dev.to", "verdict": "RELEVANTE"},
    ]
    update_feedback_cache(examples)
    shots = _format_feedback_shots()
    assert "TALVEZ" not in shots
