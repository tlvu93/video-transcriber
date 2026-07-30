"""Add unified jobs and job attempts tables.

Revision ID: 20260312_unified_jobs
Revises: 20260312_transcript_review_meta
Create Date: 2026-03-12 00:32:00
"""

from datetime import datetime
import json
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260312_unified_jobs"
down_revision = "20260312_transcript_review_meta"
branch_labels = None
depends_on = None


def _coerce_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _coerce_json(value):
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("legacy_job_table", sa.String(), nullable=False),
        sa.Column("legacy_job_id", sa.String(), nullable=False),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=True),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("legacy_job_table", "legacy_job_id", name="uq_jobs_legacy_job"),
    )
    op.create_index("ix_jobs_job_type_status_created_at", "jobs", ["job_type", "status", "created_at"], unique=False)
    op.create_index("ix_jobs_subject_type_subject_id", "jobs", ["subject_type", "subject_id"], unique=False)

    op.create_table(
        "job_attempts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("job_id", sa.String(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("processing_time_seconds", sa.Float(), nullable=True),
        sa.Column("error_details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "attempt_number", name="uq_job_attempts_job_attempt_number"),
    )
    op.create_index("ix_job_attempts_job_id_created_at", "job_attempts", ["job_id", "created_at"], unique=False)

    bind = op.get_bind()
    job_table = sa.table(
        "jobs",
        sa.column("id", sa.String()),
        sa.column("legacy_job_table", sa.String()),
        sa.column("legacy_job_id", sa.String()),
        sa.column("job_type", sa.String()),
        sa.column("subject_type", sa.String()),
        sa.column("subject_id", sa.String()),
        sa.column("status", sa.String()),
        sa.column("priority", sa.Integer()),
        sa.column("payload", sa.JSON()),
        sa.column("progress", sa.Float()),
        sa.column("attempt_count", sa.Integer()),
        sa.column("worker_id", sa.String()),
        sa.column("lease_expires_at", sa.DateTime()),
        sa.column("created_at", sa.DateTime()),
        sa.column("started_at", sa.DateTime()),
        sa.column("completed_at", sa.DateTime()),
        sa.column("processing_time_seconds", sa.Float()),
        sa.column("error_details", sa.JSON()),
    )
    attempt_table = sa.table(
        "job_attempts",
        sa.column("id", sa.String()),
        sa.column("job_id", sa.String()),
        sa.column("attempt_number", sa.Integer()),
        sa.column("worker_id", sa.String()),
        sa.column("status", sa.String()),
        sa.column("started_at", sa.DateTime()),
        sa.column("completed_at", sa.DateTime()),
        sa.column("processing_time_seconds", sa.Float()),
        sa.column("error_details", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
    )

    legacy_jobs = []
    job_attempts = []
    specs = [
        {
            "table_name": "transcription_jobs",
            "job_type": "transcription",
            "subject_type": "video",
            "subject_column": "video_id",
            "payload_builder": lambda row: {},
        },
        {
            "table_name": "summarization_jobs",
            "job_type": "summarization",
            "subject_type": "transcript",
            "subject_column": "transcript_id",
            "payload_builder": lambda row: {},
        },
        {
            "table_name": "translation_jobs",
            "job_type": "translation",
            "subject_type": "transcript",
            "subject_column": "transcript_id",
            "payload_builder": lambda row: {
                "source_language": row["source_language"],
                "target_language": row["target_language"],
            },
        },
    ]

    for spec in specs:
        rows = bind.execute(
            sa.text(
                f"""
                SELECT *
                FROM {spec["table_name"]}
                ORDER BY created_at ASC, id ASC
                """
            )
        ).mappings()

        for row in rows:
            unified_job_id = str(uuid.uuid4())
            has_attempt = row["started_at"] is not None
            attempt_count = 1 if has_attempt else 0
            legacy_jobs.append(
                {
                    "id": unified_job_id,
                    "legacy_job_table": spec["table_name"],
                    "legacy_job_id": row["id"],
                    "job_type": spec["job_type"],
                    "subject_type": spec["subject_type"],
                    "subject_id": row[spec["subject_column"]],
                    "status": row["status"],
                    "priority": 100,
                    "payload": spec["payload_builder"](row),
                    "progress": None,
                    "attempt_count": attempt_count,
                    "worker_id": row["worker_id"],
                    "lease_expires_at": _coerce_datetime(row["lease_expires_at"]),
                    "created_at": _coerce_datetime(row["created_at"]),
                    "started_at": _coerce_datetime(row["started_at"]),
                    "completed_at": _coerce_datetime(row["completed_at"]),
                    "processing_time_seconds": row["processing_time_seconds"],
                    "error_details": _coerce_json(row["error_details"]),
                }
            )
            if has_attempt:
                job_attempts.append(
                    {
                        "id": str(uuid.uuid4()),
                        "job_id": unified_job_id,
                        "attempt_number": 1,
                        "worker_id": row["worker_id"],
                        "status": row["status"],
                        "started_at": _coerce_datetime(row["started_at"]),
                        "completed_at": _coerce_datetime(row["completed_at"]),
                        "processing_time_seconds": row["processing_time_seconds"],
                        "error_details": _coerce_json(row["error_details"]),
                        "created_at": _coerce_datetime(row["created_at"]),
                    }
                )

    if legacy_jobs:
        op.bulk_insert(job_table, legacy_jobs)
    if job_attempts:
        op.bulk_insert(attempt_table, job_attempts)


def downgrade() -> None:
    op.drop_index("ix_job_attempts_job_id_created_at", table_name="job_attempts")
    op.drop_table("job_attempts")
    op.drop_index("ix_jobs_subject_type_subject_id", table_name="jobs")
    op.drop_index("ix_jobs_job_type_status_created_at", table_name="jobs")
    op.drop_table("jobs")
