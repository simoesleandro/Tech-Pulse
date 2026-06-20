"""Add content_cache column to news_items

Revision ID: 002_content_cache
Revises: 001_initial
Create Date: 2026-06-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_content_cache"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("news_items", sa.Column("content_cache", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("news_items", "content_cache")
