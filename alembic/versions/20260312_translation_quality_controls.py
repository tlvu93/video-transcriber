"""Add translation style-guide, glossary, and QA metadata.

Revision ID: 20260312_translation_qc
Revises: 20260312_normalized_segment_rows
Create Date: 2026-03-12 01:45:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_translation_qc"
down_revision = "20260312_normalized_segment_rows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("translation_jobs", sa.Column("style_guide", sa.Text(), nullable=True))
    op.add_column("translation_jobs", sa.Column("glossary_terms", sa.JSON(), nullable=True))
    op.add_column("translated_transcripts", sa.Column("style_guide", sa.Text(), nullable=True))
    op.add_column("translated_transcripts", sa.Column("glossary_terms", sa.JSON(), nullable=True))
    op.add_column("translated_transcripts", sa.Column("qa_metrics", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("translated_transcripts", "qa_metrics")
    op.drop_column("translated_transcripts", "glossary_terms")
    op.drop_column("translated_transcripts", "style_guide")
    op.drop_column("translation_jobs", "glossary_terms")
    op.drop_column("translation_jobs", "style_guide")
