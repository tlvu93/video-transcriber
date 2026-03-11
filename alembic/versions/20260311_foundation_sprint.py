"""Foundation sprint schema updates.

Revision ID: 20260311_foundation_sprint
Revises: 20250311_legacy_schema
Create Date: 2026-03-11 18:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260311_foundation_sprint"
down_revision = "20250311_legacy_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("videos") as batch_op:
            batch_op.add_column(sa.Column("storage_path", sa.String(), nullable=True))
            batch_op.create_index("ix_videos_file_hash", ["file_hash"], unique=False)
            batch_op.create_unique_constraint("uq_videos_storage_path", ["storage_path"])

        with op.batch_alter_table("transcripts") as batch_op:
            batch_op.create_index("ix_transcripts_video_id", ["video_id"], unique=False)

        with op.batch_alter_table("transcription_jobs") as batch_op:
            batch_op.add_column(sa.Column("worker_id", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
            batch_op.create_index("ix_transcription_jobs_status_created_at", ["status", "created_at"], unique=False)

        with op.batch_alter_table("summarization_jobs") as batch_op:
            batch_op.add_column(sa.Column("worker_id", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
            batch_op.create_index("ix_summarization_jobs_status_created_at", ["status", "created_at"], unique=False)

        with op.batch_alter_table("translation_jobs") as batch_op:
            batch_op.add_column(sa.Column("worker_id", sa.String(), nullable=True))
            batch_op.add_column(sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
            batch_op.create_index("ix_translation_jobs_status_created_at", ["status", "created_at"], unique=False)
    else:
        op.add_column("videos", sa.Column("storage_path", sa.String(), nullable=True))
        op.create_index("ix_videos_file_hash", "videos", ["file_hash"], unique=False)
        op.create_unique_constraint("uq_videos_storage_path", "videos", ["storage_path"])

        op.create_index("ix_transcripts_video_id", "transcripts", ["video_id"], unique=False)

        op.add_column("transcription_jobs", sa.Column("worker_id", sa.String(), nullable=True))
        op.add_column("transcription_jobs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
        op.create_index(
            "ix_transcription_jobs_status_created_at",
            "transcription_jobs",
            ["status", "created_at"],
            unique=False,
        )

        op.add_column("summarization_jobs", sa.Column("worker_id", sa.String(), nullable=True))
        op.add_column("summarization_jobs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
        op.create_index(
            "ix_summarization_jobs_status_created_at",
            "summarization_jobs",
            ["status", "created_at"],
            unique=False,
        )

        op.add_column("translation_jobs", sa.Column("worker_id", sa.String(), nullable=True))
        op.add_column("translation_jobs", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
        op.create_index(
            "ix_translation_jobs_status_created_at",
            "translation_jobs",
            ["status", "created_at"],
            unique=False,
        )
    duplicate_groups = bind.execute(
        sa.text(
            """
            SELECT transcript_id, language
            FROM translated_transcripts
            GROUP BY transcript_id, language
            HAVING COUNT(*) > 1
            """
        )
    ).fetchall()
    for transcript_id, language in duplicate_groups:
        duplicate_ids = bind.execute(
            sa.text(
                """
                SELECT id
                FROM translated_transcripts
                WHERE transcript_id = :transcript_id
                  AND language = :language
                ORDER BY created_at DESC, id DESC
                """
            ),
            {"transcript_id": transcript_id, "language": language},
        ).fetchall()
        ids_to_delete = [row[0] for row in duplicate_ids[1:]]
        if ids_to_delete:
            bind.execute(
                sa.text("DELETE FROM translated_transcripts WHERE id IN :ids").bindparams(
                    sa.bindparam("ids", expanding=True)
                ),
                {"ids": ids_to_delete},
            )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("translated_transcripts") as batch_op:
            batch_op.create_unique_constraint(
                "uq_translated_transcripts_transcript_language",
                ["transcript_id", "language"],
            )
    else:
        op.create_unique_constraint(
            "uq_translated_transcripts_transcript_language",
            "translated_transcripts",
            ["transcript_id", "language"],
        )

    op.create_table(
        "transcript_segment_search",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transcript_id", sa.String(), nullable=False),
        sa.Column("video_id", sa.String(), nullable=True),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False, server_default="0"),
        sa.Column("end_time", sa.Float(), nullable=False, server_default="0"),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transcript_id",
            "segment_id",
            name="uq_transcript_segment_search_transcript_segment",
        ),
    )
    op.create_index(
        "ix_transcript_segment_search_transcript_id",
        "transcript_segment_search",
        ["transcript_id"],
        unique=False,
    )
    op.create_index(
        "ix_transcript_segment_search_video_id",
        "transcript_segment_search",
        ["video_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_transcript_segment_search_video_id", table_name="transcript_segment_search")
    op.drop_index("ix_transcript_segment_search_transcript_id", table_name="transcript_segment_search")
    op.drop_table("transcript_segment_search")
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("translated_transcripts") as batch_op:
            batch_op.drop_constraint("uq_translated_transcripts_transcript_language", type_="unique")

        with op.batch_alter_table("translation_jobs") as batch_op:
            batch_op.drop_index("ix_translation_jobs_status_created_at")
            batch_op.drop_column("lease_expires_at")
            batch_op.drop_column("worker_id")

        with op.batch_alter_table("summarization_jobs") as batch_op:
            batch_op.drop_index("ix_summarization_jobs_status_created_at")
            batch_op.drop_column("lease_expires_at")
            batch_op.drop_column("worker_id")

        with op.batch_alter_table("transcription_jobs") as batch_op:
            batch_op.drop_index("ix_transcription_jobs_status_created_at")
            batch_op.drop_column("lease_expires_at")
            batch_op.drop_column("worker_id")

        with op.batch_alter_table("transcripts") as batch_op:
            batch_op.drop_index("ix_transcripts_video_id")

        with op.batch_alter_table("videos") as batch_op:
            batch_op.drop_constraint("uq_videos_storage_path", type_="unique")
            batch_op.drop_index("ix_videos_file_hash")
            batch_op.drop_column("storage_path")
    else:
        op.drop_constraint(
            "uq_translated_transcripts_transcript_language",
            "translated_transcripts",
            type_="unique",
        )
        op.drop_index("ix_translation_jobs_status_created_at", table_name="translation_jobs")
        op.drop_column("translation_jobs", "lease_expires_at")
        op.drop_column("translation_jobs", "worker_id")
        op.drop_index("ix_summarization_jobs_status_created_at", table_name="summarization_jobs")
        op.drop_column("summarization_jobs", "lease_expires_at")
        op.drop_column("summarization_jobs", "worker_id")
        op.drop_index("ix_transcription_jobs_status_created_at", table_name="transcription_jobs")
        op.drop_column("transcription_jobs", "lease_expires_at")
        op.drop_column("transcription_jobs", "worker_id")
        op.drop_index("ix_transcripts_video_id", table_name="transcripts")
        op.drop_constraint("uq_videos_storage_path", "videos", type_="unique")
        op.drop_index("ix_videos_file_hash", table_name="videos")
        op.drop_column("videos", "storage_path")
