"""Add PostgreSQL search indexes for transcript segment search.

Revision ID: 20260311_search_perf_indexes
Revises: 20260311_foundation_sprint
Create Date: 2026-03-11 20:05:00
"""

from alembic import op


revision = "20260311_search_perf_indexes"
down_revision = "20260311_foundation_sprint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_transcript_segment_search_text_trgm
        ON transcript_segment_search
        USING gin (text gin_trgm_ops)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_transcript_segment_search_text_fts
        ON transcript_segment_search
        USING gin (to_tsvector('simple', text))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_transcript_segment_search_text_fts")
    op.execute("DROP INDEX IF EXISTS ix_transcript_segment_search_text_trgm")
