"""Add FTS5 virtual table for full-text search

Revision ID: 005
Revises: 003
Create Date: 2026-06-20
"""
from alembic import op

revision = "005_fts5_search"
down_revision = "004_missing_indexes"
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
