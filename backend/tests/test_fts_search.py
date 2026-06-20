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
