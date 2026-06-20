"""add missing news_items indexes

Revision ID: 004_missing_indexes
Revises: 003_user_relevance
Create Date: 2026-06-20

"""
from alembic import op

revision = "004_missing_indexes"
down_revision = "003_user_relevance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("idx_news_folder", "news_items", ["folder_id"])
    op.create_index("idx_news_source", "news_items", ["source"])
    op.create_index("idx_news_obsidian", "news_items", ["obsidian_exported_at"])
    op.create_index("idx_news_hype", "news_items", ["hype_score"])
    op.create_index("idx_news_created", "news_items", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_news_created", table_name="news_items")
    op.drop_index("idx_news_hype", table_name="news_items")
    op.drop_index("idx_news_obsidian", table_name="news_items")
    op.drop_index("idx_news_source", table_name="news_items")
    op.drop_index("idx_news_folder", table_name="news_items")
