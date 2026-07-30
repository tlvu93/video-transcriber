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
    bind = op.get_bind()
    op.add_column(
        "summaries",
        sa.Column("content_profile", sa.String(), nullable=True),
    )
    op.add_column(
        "summaries",
        sa.Column("summary_metadata", sa.JSON(), nullable=True),
    )
    op.execute("UPDATE summaries SET content_profile = 'generic' WHERE content_profile IS NULL")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("summaries") as batch_op:
            batch_op.alter_column("content_profile", existing_type=sa.String(), nullable=False)
    else:
        op.alter_column("summaries", "content_profile", nullable=False)

    op.add_column(
        "summarization_jobs",
        sa.Column("content_profile", sa.String(), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_column("summarization_jobs", "content_profile")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("summaries") as batch_op:
            batch_op.drop_column("summary_metadata")
            batch_op.drop_column("content_profile")
    else:
        op.drop_column("summaries", "summary_metadata")
        op.drop_column("summaries", "content_profile")
