"""Add normalized transcript and translated transcript segment tables.

Revision ID: 20260312_normalized_segment_rows
Revises: 20260312_unified_jobs
Create Date: 2026-03-12 01:05:00
"""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any, Dict, List

from alembic import op
import sqlalchemy as sa


revision = "20260312_normalized_segment_rows"
down_revision = "20260312_unified_jobs"
branch_labels = None
depends_on = None


def _coerce_datetime(value: Any) -> Any:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return value
    return value


def _normalize_segment_id(raw_segment_id: Any, fallback_index: int) -> int:
    try:
        return int(raw_segment_id)
    except (TypeError, ValueError):
        return fallback_index


def _normalize_segments(raw_segments: Any, fallback_content: str | None) -> List[Dict[str, Any]]:
    if isinstance(raw_segments, str):
        try:
            raw_segments = json.loads(raw_segments)
        except json.JSONDecodeError:
            raw_segments = []

    segments = raw_segments if isinstance(raw_segments, list) else []
    if not segments and fallback_content:
        segments = [
            {
                "id": 1,
                "start_time": 0,
                "end_time": 0,
                "text": fallback_content,
                "speaker": None,
            }
        ]

    normalized: List[Dict[str, Any]] = []
    seen_segment_ids: set[int] = set()

    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue

        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        segment_id = _normalize_segment_id(segment.get("id"), index)
        while segment_id in seen_segment_ids:
            segment_id += 1

        seen_segment_ids.add(segment_id)
        speaker = str(segment.get("speaker")).strip() if segment.get("speaker") else None

        normalized.append(
            {
                "segment_id": segment_id,
                "segment_index": index,
                "start_time": float(segment.get("start_time", 0) or 0),
                "end_time": float(segment.get("end_time", 0) or 0),
                "text": text,
                "speaker": speaker or None,
            }
        )

    return normalized


def upgrade() -> None:
    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("transcript_id", sa.String(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transcript_id",
            "segment_id",
            name="uq_transcript_segments_transcript_segment",
        ),
    )
    op.create_index(
        "ix_transcript_segments_transcript_index",
        "transcript_segments",
        ["transcript_id", "segment_index"],
        unique=False,
    )

    op.create_table(
        "translated_transcript_segments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("translated_transcript_id", sa.String(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Float(), nullable=False),
        sa.Column("end_time", sa.Float(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("speaker", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["translated_transcript_id"], ["translated_transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "translated_transcript_id",
            "segment_id",
            name="uq_translated_transcript_segments_segment",
        ),
    )
    op.create_index(
        "ix_translated_transcript_segments_transcript_index",
        "translated_transcript_segments",
        ["translated_transcript_id", "segment_index"],
        unique=False,
    )

    bind = op.get_bind()
    transcript_segment_table = sa.table(
        "transcript_segments",
        sa.column("transcript_id", sa.String()),
        sa.column("segment_id", sa.Integer()),
        sa.column("segment_index", sa.Integer()),
        sa.column("start_time", sa.Float()),
        sa.column("end_time", sa.Float()),
        sa.column("text", sa.Text()),
        sa.column("speaker", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    translated_segment_table = sa.table(
        "translated_transcript_segments",
        sa.column("translated_transcript_id", sa.String()),
        sa.column("segment_id", sa.Integer()),
        sa.column("segment_index", sa.Integer()),
        sa.column("start_time", sa.Float()),
        sa.column("end_time", sa.Float()),
        sa.column("text", sa.Text()),
        sa.column("speaker", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    transcript_rows = bind.execute(
        sa.text(
            """
            SELECT id, content, segments, created_at
            FROM transcripts
            ORDER BY created_at ASC, id ASC
            """
        )
    ).mappings()
    transcript_segment_rows = []
    for row in transcript_rows:
        for segment in _normalize_segments(row["segments"], row["content"]):
            transcript_segment_rows.append(
                {
                    "transcript_id": row["id"],
                    "segment_id": segment["segment_id"],
                    "segment_index": segment["segment_index"],
                    "start_time": segment["start_time"],
                    "end_time": segment["end_time"],
                    "text": segment["text"],
                    "speaker": segment["speaker"],
                    "created_at": _coerce_datetime(row["created_at"]),
                    "updated_at": _coerce_datetime(row["created_at"]),
                }
            )

    translated_rows = bind.execute(
        sa.text(
            """
            SELECT id, content, segments, created_at
            FROM translated_transcripts
            ORDER BY created_at ASC, id ASC
            """
        )
    ).mappings()
    translated_segment_rows = []
    for row in translated_rows:
        for segment in _normalize_segments(row["segments"], row["content"]):
            translated_segment_rows.append(
                {
                    "translated_transcript_id": row["id"],
                    "segment_id": segment["segment_id"],
                    "segment_index": segment["segment_index"],
                    "start_time": segment["start_time"],
                    "end_time": segment["end_time"],
                    "text": segment["text"],
                    "speaker": segment["speaker"],
                    "created_at": _coerce_datetime(row["created_at"]),
                    "updated_at": _coerce_datetime(row["created_at"]),
                }
            )

    if transcript_segment_rows:
        op.bulk_insert(transcript_segment_table, transcript_segment_rows)

    if translated_segment_rows:
        op.bulk_insert(translated_segment_table, translated_segment_rows)


def downgrade() -> None:
    op.drop_index(
        "ix_translated_transcript_segments_transcript_index",
        table_name="translated_transcript_segments",
    )
    op.drop_table("translated_transcript_segments")
    op.drop_index(
        "ix_transcript_segments_transcript_index",
        table_name="transcript_segments",
    )
    op.drop_table("transcript_segments")
