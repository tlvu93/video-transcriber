"""Add transcript review fields and comments.

Revision ID: 20260312_transcript_review_meta
Revises: 20260311_transcript_revisions
Create Date: 2026-03-12 00:18:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260312_transcript_review_meta"
down_revision = "20260311_transcript_revisions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transcripts", sa.Column("review_status", sa.String(), nullable=True))
    op.add_column("transcripts", sa.Column("review_assignee", sa.String(), nullable=True))
    op.execute("UPDATE transcripts SET review_status = 'draft' WHERE review_status IS NULL")
    op.alter_column("transcripts", "review_status", nullable=False)

    op.create_table(
        "transcript_comments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("transcript_id", sa.String(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=True),
        sa.Column("timestamp_seconds", sa.Float(), nullable=True),
        sa.Column("author_name", sa.String(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transcript_comments_transcript_created_at",
        "transcript_comments",
        ["transcript_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_comments_transcript_created_at", table_name="transcript_comments")
    op.drop_table("transcript_comments")
    op.drop_column("transcripts", "review_assignee")
    op.drop_column("transcripts", "review_status")
