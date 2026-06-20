"""Add user_relevance column to news_items

Revision ID: 003_user_relevance
Revises: 002_content_cache
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_user_relevance"
down_revision: Union[str, None] = "002_content_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column("user_relevance", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("news_items", "user_relevance")
