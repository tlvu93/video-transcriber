"""Add normalized metadata tables for storage, speakers, summaries, and localization.

Revision ID: 20260312_norm_metadata_tables
Revises: 20260312_translation_qc
Create Date: 2026-03-12 05:10:00
"""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any, Dict, List

from alembic import op
import sqlalchemy as sa


revision = "20260312_norm_metadata_tables"
down_revision = "20260312_translation_qc"
branch_labels = None
depends_on = None


def _normalize_segment_id(raw_segment_id: Any, fallback_index: int) -> int:
    try:
        return int(raw_segment_id)
    except (TypeError, ValueError):
        return fallback_index


def _normalize_segments(raw_segments: Any) -> List[Dict[str, Any]]:
    segments = raw_segments if isinstance(raw_segments, list) else []
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
                "speaker": speaker or None,
            }
        )

    return normalized


def _normalize_speaker_aliases(raw_aliases: Any) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    if not isinstance(raw_aliases, dict):
        return normalized

    for raw_speaker_id, raw_display_name in raw_aliases.items():
        speaker_key = str(raw_speaker_id).strip()
        if not speaker_key:
            continue

        display_name = str(raw_display_name).strip() if raw_display_name is not None else ""
        normalized[speaker_key] = display_name or speaker_key

    return normalized


def _normalize_glossary_terms(raw_terms: Any) -> List[Dict[str, str]]:
    normalized_terms: List[Dict[str, str]] = []
    for raw_term in raw_terms or []:
        if not isinstance(raw_term, dict):
            continue

        source_term = str(raw_term.get("source_term", "")).strip()
        target_term = str(raw_term.get("target_term", "")).strip()
        if not source_term or not target_term:
            continue

        normalized_term = {
            "source_term": source_term,
            "target_term": target_term,
        }
        notes = str(raw_term.get("notes", "")).strip()
        if notes:
            normalized_term["notes"] = notes

        normalized_terms.append(normalized_term)

    return normalized_terms


def upgrade() -> None:
    op.create_table(
        "video_storage_objects",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("video_id", sa.String(), nullable=False),
        sa.Column("storage_backend", sa.String(), nullable=False),
        sa.Column("storage_uri", sa.String(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["video_id"], ["videos.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "storage_backend",
            "storage_uri",
            name="uq_video_storage_objects_backend_uri",
        ),
    )
    op.create_index(
        "ix_video_storage_objects_video_primary",
        "video_storage_objects",
        ["video_id", "is_primary"],
        unique=False,
    )

    op.create_table(
        "speakers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("transcript_id", sa.String(), nullable=False),
        sa.Column("speaker_key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "transcript_id",
            "speaker_key",
            name="uq_speakers_transcript_key",
        ),
    )
    op.create_index(
        "ix_speakers_transcript_display_name",
        "speakers",
        ["transcript_id", "display_name"],
        unique=False,
    )

    op.create_table(
        "summary_variants",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("summary_id", sa.String(), nullable=False),
        sa.Column("variant_type", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["summary_id"], ["summaries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "summary_id",
            "variant_type",
            name="uq_summary_variants_summary_variant_type",
        ),
    )

    op.create_table(
        "style_guides",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("translated_transcript_id", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["translated_transcript_id"], ["translated_transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "translated_transcript_id",
            name="uq_style_guides_translated_transcript",
        ),
    )

    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("translated_transcript_id", sa.String(), nullable=False),
        sa.Column("source_term", sa.String(), nullable=False),
        sa.Column("target_term", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["translated_transcript_id"], ["translated_transcripts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_glossary_terms_translated_transcript_sort",
        "glossary_terms",
        ["translated_transcript_id", "sort_order"],
        unique=False,
    )

    bind = op.get_bind()
    now = datetime.utcnow()

    video_table = sa.table(
        "videos",
        sa.column("id", sa.String()),
        sa.column("storage_path", sa.String()),
        sa.column("file_hash", sa.String()),
        sa.column("created_at", sa.DateTime()),
    )
    video_storage_object_table = sa.table(
        "video_storage_objects",
        sa.column("id", sa.String()),
        sa.column("video_id", sa.String()),
        sa.column("storage_backend", sa.String()),
        sa.column("storage_uri", sa.String()),
        sa.column("content_hash", sa.String()),
        sa.column("is_primary", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    transcript_table = sa.table(
        "transcripts",
        sa.column("id", sa.String()),
        sa.column("speaker_aliases", sa.JSON()),
        sa.column("segments", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
    )
    speaker_table = sa.table(
        "speakers",
        sa.column("id", sa.String()),
        sa.column("transcript_id", sa.String()),
        sa.column("speaker_key", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    summary_table = sa.table(
        "summaries",
        sa.column("id", sa.String()),
        sa.column("content", sa.Text()),
        sa.column("created_at", sa.DateTime()),
    )
    summary_variant_table = sa.table(
        "summary_variants",
        sa.column("id", sa.String()),
        sa.column("summary_id", sa.String()),
        sa.column("variant_type", sa.String()),
        sa.column("content", sa.Text()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    translated_transcript_table = sa.table(
        "translated_transcripts",
        sa.column("id", sa.String()),
        sa.column("style_guide", sa.Text()),
        sa.column("glossary_terms", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
    )
    style_guide_table = sa.table(
        "style_guides",
        sa.column("id", sa.String()),
        sa.column("translated_transcript_id", sa.String()),
        sa.column("content", sa.Text()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    glossary_term_table = sa.table(
        "glossary_terms",
        sa.column("id", sa.String()),
        sa.column("translated_transcript_id", sa.String()),
        sa.column("source_term", sa.String()),
        sa.column("target_term", sa.String()),
        sa.column("notes", sa.Text()),
        sa.column("sort_order", sa.Integer()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )

    storage_rows = []
    for row in bind.execute(sa.select(video_table.c.id, video_table.c.storage_path, video_table.c.file_hash, video_table.c.created_at)):
        if not row.storage_path:
            continue
        storage_rows.append(
            {
                "id": str(uuid.uuid4()),
                "video_id": row.id,
                "storage_backend": "local_fs",
                "storage_uri": row.storage_path,
                "content_hash": row.file_hash,
                "is_primary": True,
                "created_at": row.created_at or now,
                "updated_at": row.created_at or now,
            }
        )
    if storage_rows:
        op.bulk_insert(video_storage_object_table, storage_rows)

    speaker_rows = []
    for row in bind.execute(sa.select(transcript_table.c.id, transcript_table.c.speaker_aliases, transcript_table.c.segments, transcript_table.c.created_at)):
        normalized_aliases = _normalize_speaker_aliases(row.speaker_aliases)
        speaker_keys = set(normalized_aliases.keys())
        for segment in _normalize_segments(row.segments):
            speaker = segment.get("speaker")
            if speaker:
                speaker_keys.add(speaker)

        for speaker_key in sorted(speaker_key for speaker_key in speaker_keys if speaker_key):
            speaker_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "transcript_id": row.id,
                    "speaker_key": speaker_key,
                    "display_name": normalized_aliases.get(speaker_key, speaker_key),
                    "created_at": row.created_at or now,
                    "updated_at": row.created_at or now,
                }
            )
    if speaker_rows:
        op.bulk_insert(speaker_table, speaker_rows)

    summary_variant_rows = []
    for row in bind.execute(sa.select(summary_table.c.id, summary_table.c.content, summary_table.c.created_at)):
        summary_variant_rows.append(
            {
                "id": str(uuid.uuid4()),
                "summary_id": row.id,
                "variant_type": "default",
                "content": row.content,
                "created_at": row.created_at or now,
                "updated_at": row.created_at or now,
            }
        )
    if summary_variant_rows:
        op.bulk_insert(summary_variant_table, summary_variant_rows)

    style_guide_rows = []
    glossary_term_rows = []
    for row in bind.execute(
        sa.select(
            translated_transcript_table.c.id,
            translated_transcript_table.c.style_guide,
            translated_transcript_table.c.glossary_terms,
            translated_transcript_table.c.created_at,
        )
    ):
        created_at = row.created_at or now
        style_guide = str(row.style_guide).strip() if row.style_guide else ""
        if style_guide:
            style_guide_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "translated_transcript_id": row.id,
                    "content": style_guide,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

        for index, term in enumerate(_normalize_glossary_terms(row.glossary_terms), start=1):
            glossary_term_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "translated_transcript_id": row.id,
                    "source_term": term["source_term"],
                    "target_term": term["target_term"],
                    "notes": term.get("notes"),
                    "sort_order": index,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )

    if style_guide_rows:
        op.bulk_insert(style_guide_table, style_guide_rows)
    if glossary_term_rows:
        op.bulk_insert(glossary_term_table, glossary_term_rows)


def downgrade() -> None:
    op.drop_index("ix_glossary_terms_translated_transcript_sort", table_name="glossary_terms")
    op.drop_table("glossary_terms")
    op.drop_table("style_guides")
    op.drop_table("summary_variants")
    op.drop_index("ix_speakers_transcript_display_name", table_name="speakers")
    op.drop_table("speakers")
    op.drop_index("ix_video_storage_objects_video_primary", table_name="video_storage_objects")
    op.drop_table("video_storage_objects")
