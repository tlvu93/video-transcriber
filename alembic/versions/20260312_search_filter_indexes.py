"""Add supporting indexes for filtered transcript search.

Revision ID: 20260312_search_filter_indexes
Revises: 20260312_norm_metadata_tables
Create Date: 2026-03-12 12:15:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260312_search_filter_indexes"
down_revision = "20260312_norm_metadata_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_videos_filename", "videos", ["filename"], unique=False)
    op.create_index("ix_transcripts_language_code", "transcripts", ["language_code"], unique=False)
    op.create_index("ix_transcripts_review_status", "transcripts", ["review_status"], unique=False)
    op.create_index(
        "ix_transcript_segment_search_speaker",
        "transcript_segment_search",
        ["speaker"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_segment_search_speaker", table_name="transcript_segment_search")
    op.drop_index("ix_transcripts_review_status", table_name="transcripts")
    op.drop_index("ix_transcripts_language_code", table_name="transcripts")
    op.drop_index("ix_videos_filename", table_name="videos")
