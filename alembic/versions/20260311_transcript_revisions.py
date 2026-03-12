"""Add transcript revisions and server-side speaker aliases.

Revision ID: 20260311_transcript_revisions
Revises: 20260311_search_perf_indexes
Create Date: 2026-03-11 23:58:00
"""

import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260311_transcript_revisions"
down_revision = "20260311_search_perf_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("transcripts", sa.Column("speaker_aliases", sa.JSON(), nullable=True))
    op.create_table(
        "transcript_revisions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("transcript_id", sa.String(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("segments", sa.JSON(), nullable=True),
        sa.Column("speaker_aliases", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transcript_id",
            "revision_number",
            name="uq_transcript_revisions_transcript_revision_number",
        ),
    )
    op.create_index(
        "ix_transcript_revisions_transcript_created_at",
        "transcript_revisions",
        ["transcript_id", "created_at"],
        unique=False,
    )

    bind = op.get_bind()
    transcripts = bind.execute(
        sa.text(
            """
            SELECT id, content, segments, speaker_aliases, created_at
            FROM transcripts
            ORDER BY created_at ASC, id ASC
            """
        )
    ).mappings()

    transcript_revisions_table = sa.table(
        "transcript_revisions",
        sa.column("id", sa.String()),
        sa.column("transcript_id", sa.String()),
        sa.column("revision_number", sa.Integer()),
        sa.column("reason", sa.String()),
        sa.column("content", sa.Text()),
        sa.column("segments", sa.JSON()),
        sa.column("speaker_aliases", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
    )

    revision_rows = []
    for row in transcripts:
        revision_rows.append(
            {
                "id": str(uuid.uuid4()),
                "transcript_id": row["id"],
                "revision_number": 1,
                "reason": "initial_import",
                "content": row["content"],
                "segments": row["segments"],
                "speaker_aliases": row["speaker_aliases"] or {},
                "created_at": row["created_at"],
            }
        )

    if revision_rows:
        op.bulk_insert(transcript_revisions_table, revision_rows)


def downgrade() -> None:
    op.drop_index("ix_transcript_revisions_transcript_created_at", table_name="transcript_revisions")
    op.drop_table("transcript_revisions")
    op.drop_column("transcripts", "speaker_aliases")
