"""Add scraper_runs table for source health monitoring

Revision ID: 004
Revises: 003
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "006_scraper_runs"
down_revision = "005_fts5_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("items_found", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.String, nullable=True),
    )
    op.create_index("idx_scraper_runs_source", "scraper_runs", ["source"])
    op.create_index("idx_scraper_runs_started", "scraper_runs", ["started_at"])


def downgrade() -> None:
    op.drop_index("idx_scraper_runs_started", table_name="scraper_runs")
    op.drop_index("idx_scraper_runs_source", table_name="scraper_runs")
    op.drop_table("scraper_runs")
