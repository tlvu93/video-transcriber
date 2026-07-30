"""Drop legacy per-job tables after unified-job cutover.

Revision ID: 20260315_drop_legacy_job_tables
Revises: 20260315_job_payload_backfill
Create Date: 2026-03-15 02:10:00
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20260315_drop_legacy_job_tables"
down_revision = "20260315_job_payload_backfill"
branch_labels = None
depends_on = None


def _coerce_payload(value):
    if isinstance(value, dict):
        return dict(value)
    if not value:
        return {}
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return dict(value)


def _json_param(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


def upgrade() -> None:
    op.drop_table("translation_jobs")
    op.drop_table("summarization_jobs")
    op.drop_table("transcription_jobs")


def downgrade() -> None:
    op.create_table(
        "transcription_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("video_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transcription_jobs_status_created_at",
        "transcription_jobs",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "summarization_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("transcript_id", sa.String(), nullable=False),
        sa.Column("content_profile", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_summarization_jobs_status_created_at",
        "summarization_jobs",
        ["status", "created_at"],
        unique=False,
    )

    op.create_table(
        "translation_jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("transcript_id", sa.String(), nullable=False),
        sa.Column("source_language", sa.String(), nullable=True),
        sa.Column("target_language", sa.String(), nullable=False),
        sa.Column("style_guide", sa.Text(), nullable=True),
        sa.Column("glossary_terms", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_translation_jobs_status_created_at",
        "translation_jobs",
        ["status", "created_at"],
        unique=False,
    )

    bind = op.get_bind()
    transcription_rows = bind.execute(
        sa.text(
            """
            SELECT legacy_job_id AS id, subject_id AS video_id, status, created_at, started_at,
                   completed_at, processing_time_seconds, error_details, worker_id, lease_expires_at
            FROM jobs
            WHERE job_type = 'transcription'
            """
        )
    ).mappings()
    for row in transcription_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO transcription_jobs
                    (id, video_id, status, created_at, started_at, completed_at,
                     processing_time_seconds, error_details, worker_id, lease_expires_at)
                VALUES
                    (:id, :video_id, :status, :created_at, :started_at, :completed_at,
                     :processing_time_seconds, :error_details, :worker_id, :lease_expires_at)
                """
            ),
            {
                **dict(row),
                "error_details": _json_param(row["error_details"]),
            },
        )

    summarization_rows = bind.execute(
        sa.text(
            """
            SELECT
                legacy_job_id AS id,
                subject_id AS transcript_id,
                payload,
                status,
                created_at,
                started_at,
                completed_at,
                processing_time_seconds,
                error_details,
                worker_id,
                lease_expires_at
            FROM jobs
            WHERE job_type = 'summarization'
            """
        )
    ).mappings()
    for row in summarization_rows:
        payload = _coerce_payload(row["payload"])
        bind.execute(
            sa.text(
                """
                INSERT INTO summarization_jobs
                    (id, transcript_id, content_profile, status, created_at, started_at,
                     completed_at, processing_time_seconds, error_details, worker_id, lease_expires_at)
                VALUES
                    (:id, :transcript_id, :content_profile, :status, :created_at, :started_at,
                     :completed_at, :processing_time_seconds, :error_details, :worker_id, :lease_expires_at)
                """
            ),
            {
                "id": row["id"],
                "transcript_id": row["transcript_id"],
                "content_profile": payload.get("content_profile"),
                "status": row["status"],
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "processing_time_seconds": row["processing_time_seconds"],
                "error_details": _json_param(row["error_details"]),
                "worker_id": row["worker_id"],
                "lease_expires_at": row["lease_expires_at"],
            },
        )

    translation_rows = bind.execute(
        sa.text(
            """
            SELECT
                legacy_job_id AS id,
                subject_id AS transcript_id,
                payload,
                status,
                created_at,
                started_at,
                completed_at,
                processing_time_seconds,
                error_details,
                worker_id,
                lease_expires_at
            FROM jobs
            WHERE job_type = 'translation'
            """
        )
    ).mappings()
    for row in translation_rows:
        payload = _coerce_payload(row["payload"])
        bind.execute(
            sa.text(
                """
                INSERT INTO translation_jobs
                    (id, transcript_id, source_language, target_language, style_guide, glossary_terms,
                     status, created_at, started_at, completed_at, processing_time_seconds,
                     error_details, worker_id, lease_expires_at)
                VALUES
                    (:id, :transcript_id, :source_language, :target_language, :style_guide, :glossary_terms,
                     :status, :created_at, :started_at, :completed_at, :processing_time_seconds,
                     :error_details, :worker_id, :lease_expires_at)
                """
            ),
            {
                "id": row["id"],
                "transcript_id": row["transcript_id"],
                "source_language": payload.get("source_language"),
                "target_language": payload.get("target_language"),
                "style_guide": payload.get("style_guide"),
                "glossary_terms": _json_param(payload.get("glossary_terms") or []),
                "status": row["status"],
                "created_at": row["created_at"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "processing_time_seconds": row["processing_time_seconds"],
                "error_details": _json_param(row["error_details"]),
                "worker_id": row["worker_id"],
                "lease_expires_at": row["lease_expires_at"],
            },
        )
