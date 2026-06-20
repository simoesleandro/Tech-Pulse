"""Add embedding column to news_items

Revision ID: 007_embedding
Revises: 003_user_relevance
Create Date: 2026-06-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007_embedding"
down_revision: Union[str, None] = "003_user_relevance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "news_items",
        sa.Column("embedding", sa.LargeBinary, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("news_items", "embedding")
