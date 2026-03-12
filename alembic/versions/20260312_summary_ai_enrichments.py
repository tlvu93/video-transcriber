"""Add summary enrichment metadata and summarization content-profile overrides.

Revision ID: 20260312_summary_ai_enrichments
Revises: 20260312_search_filter_indexes
Create Date: 2026-03-12 15:20:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_summary_ai_enrichments"
down_revision = "20260312_search_filter_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "summaries",
        sa.Column("content_profile", sa.String(), nullable=True),
    )
    op.add_column(
        "summaries",
        sa.Column("summary_metadata", sa.JSON(), nullable=True),
    )
    op.execute("UPDATE summaries SET content_profile = 'generic' WHERE content_profile IS NULL")
    op.alter_column("summaries", "content_profile", nullable=False)

    op.add_column(
        "summarization_jobs",
        sa.Column("content_profile", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("summarization_jobs", "content_profile")
    op.drop_column("summaries", "summary_metadata")
    op.drop_column("summaries", "content_profile")
