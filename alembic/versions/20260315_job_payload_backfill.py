"""Backfill unified job payloads with legacy compatibility fields.

Revision ID: 20260315_job_payload_backfill
Revises: 20260312_operational_metrics
Create Date: 2026-03-15 00:40:00
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20260315_job_payload_backfill"
down_revision = "20260312_operational_metrics"
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


def upgrade() -> None:
    bind = op.get_bind()
    jobs_table = sa.table(
        "jobs",
        sa.column("id", sa.String()),
        sa.column("payload", sa.JSON()),
    )

    transcription_rows = bind.execute(
        sa.text(
            """
            SELECT jobs.id, jobs.payload, transcription_jobs.video_id
            FROM jobs
            JOIN transcription_jobs ON transcription_jobs.id = jobs.legacy_job_id
            WHERE jobs.job_type = 'transcription'
            """
        )
    ).mappings()
    for row in transcription_rows:
        payload = _coerce_payload(row["payload"])
        payload["video_id"] = row["video_id"]
        bind.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == row["id"])
            .values(payload=payload)
        )

    summarization_rows = bind.execute(
        sa.text(
            """
            SELECT jobs.id, jobs.payload, summarization_jobs.transcript_id, summarization_jobs.content_profile
            FROM jobs
            JOIN summarization_jobs ON summarization_jobs.id = jobs.legacy_job_id
            WHERE jobs.job_type = 'summarization'
            """
        )
    ).mappings()
    for row in summarization_rows:
        payload = _coerce_payload(row["payload"])
        payload["transcript_id"] = row["transcript_id"]
        if row["content_profile"]:
            payload["content_profile"] = row["content_profile"]
        bind.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == row["id"])
            .values(payload=payload)
        )

    translation_rows = bind.execute(
        sa.text(
            """
            SELECT
                jobs.id,
                jobs.payload,
                translation_jobs.transcript_id,
                translation_jobs.source_language,
                translation_jobs.target_language,
                translation_jobs.style_guide,
                translation_jobs.glossary_terms
            FROM jobs
            JOIN translation_jobs ON translation_jobs.id = jobs.legacy_job_id
            WHERE jobs.job_type = 'translation'
            """
        )
    ).mappings()
    for row in translation_rows:
        payload = _coerce_payload(row["payload"])
        payload["transcript_id"] = row["transcript_id"]
        payload["source_language"] = row["source_language"]
        payload["target_language"] = row["target_language"]
        if row["style_guide"]:
            payload["style_guide"] = row["style_guide"]
        if isinstance(row["glossary_terms"], str):
            try:
                payload["glossary_terms"] = json.loads(row["glossary_terms"]) or []
            except json.JSONDecodeError:
                payload["glossary_terms"] = []
        else:
            payload["glossary_terms"] = row["glossary_terms"] or []
        bind.execute(
            sa.update(jobs_table)
            .where(jobs_table.c.id == row["id"])
            .values(payload=payload)
        )


def downgrade() -> None:
    # The payload enrichment is backward-compatible and safe to keep on downgrade.
    pass
