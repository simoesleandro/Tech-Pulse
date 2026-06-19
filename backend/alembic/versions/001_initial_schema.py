"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2026-06-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "topic_folders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "news_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("title_original", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("ai_relevance", sa.String(), nullable=False),
        sa.Column("hype_score", sa.Integer(), server_default="0", nullable=False),
        sa.Column("ai_reasoning", sa.String(), nullable=True),
        sa.Column("engagement_reactions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("engagement_comments", sa.Integer(), server_default="0", nullable=False),
        sa.Column("engagement_stars", sa.Integer(), server_default="0", nullable=False),
        sa.Column("engagement_ups", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_enriched", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("is_read", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("is_bookmarked", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("folder_id", sa.Integer(), nullable=True),
        sa.Column("obsidian_exported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=True),
        sa.ForeignKeyConstraint(["folder_id"], ["topic_folders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url"),
    )
    op.create_index("idx_news_unread", "news_items", ["is_read", "ai_relevance"])


def downgrade() -> None:
    op.drop_index("idx_news_unread", table_name="news_items")
    op.drop_table("news_items")
    op.drop_table("topic_folders")
