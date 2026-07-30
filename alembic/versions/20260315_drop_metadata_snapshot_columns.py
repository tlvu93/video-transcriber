"""Drop duplicated metadata snapshot columns after canonical cutover.

Revision ID: 20260315_drop_metadata_snapshots
Revises: 20260315_drop_legacy_job_tables
Create Date: 2026-03-15 05:20:00
"""

from __future__ import annotations

from datetime import datetime
import json
from urllib.parse import urlparse
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260315_drop_metadata_snapshots"
down_revision = "20260315_drop_legacy_job_tables"
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


def _json_param(value):
    if value is None or isinstance(value, str):
        return value
    return json.dumps(value)


def _normalize_segment_id(raw_segment_id, fallback_index):
    try:
        return int(raw_segment_id)
    except (TypeError, ValueError):
        return fallback_index


def _normalize_segments(raw_segments, fallback_content):
    raw_segments = _coerce_json(raw_segments)
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

    normalized = []
    seen_segment_ids = set()
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


def _normalize_speaker_aliases(raw_aliases):
    raw_aliases = _coerce_json(raw_aliases)
    normalized = {}
    if not isinstance(raw_aliases, dict):
        return normalized

    for raw_key, raw_value in raw_aliases.items():
        speaker_key = str(raw_key).strip()
        if not speaker_key:
            continue
        display_name = str(raw_value).strip() if raw_value is not None else ""
        normalized[speaker_key] = display_name or speaker_key

    return normalized


def _normalize_style_guide(raw_style_guide):
    if raw_style_guide is None:
        return None
    style_guide = str(raw_style_guide).strip()
    return style_guide or None


def _normalize_glossary_terms(raw_terms):
    raw_terms = _coerce_json(raw_terms)
    normalized_terms = []
    for raw_term in raw_terms or []:
        if not isinstance(raw_term, dict):
            continue

        source_term = str(raw_term.get("source_term", "")).strip()
        target_term = str(raw_term.get("target_term", "")).strip()
        if not source_term or not target_term:
            continue

        term = {
            "source_term": source_term,
            "target_term": target_term,
        }
        notes = str(raw_term.get("notes", "")).strip()
        if notes:
            term["notes"] = notes
        normalized_terms.append(term)

    return normalized_terms


def _backfill_video_storage_objects(bind) -> None:
    video_rows = bind.execute(
        sa.text(
            """
            SELECT id, storage_path, file_hash, created_at
            FROM videos
            WHERE storage_path IS NOT NULL AND storage_path != ''
            """
        )
    ).mappings()
    for row in video_rows:
        storage_uri = str(row["storage_path"]).strip()
        if not storage_uri:
            continue

        storage_backend = "s3_compatible" if urlparse(storage_uri).scheme == "s3" else "local_fs"
        existing = bind.execute(
            sa.text(
                """
                SELECT id
                FROM video_storage_objects
                WHERE storage_backend = :storage_backend
                  AND storage_uri = :storage_uri
                """
            ),
            {
                "storage_backend": storage_backend,
                "storage_uri": storage_uri,
            },
        ).mappings().first()

        if existing is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO video_storage_objects
                        (id, video_id, storage_backend, storage_uri, content_hash, is_primary, created_at, updated_at)
                    VALUES
                        (:id, :video_id, :storage_backend, :storage_uri, :content_hash, :is_primary, :created_at, :updated_at)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "video_id": row["id"],
                    "storage_backend": storage_backend,
                    "storage_uri": storage_uri,
                    "content_hash": row["file_hash"],
                    "is_primary": True,
                    "created_at": _coerce_datetime(row["created_at"]),
                    "updated_at": _coerce_datetime(row["created_at"]),
                },
            )
        else:
            bind.execute(
                sa.text(
                    """
                    UPDATE video_storage_objects
                    SET video_id = :video_id,
                        content_hash = :content_hash,
                        is_primary = :is_primary
                    WHERE id = :id
                    """
                ),
                {
                    "id": existing["id"],
                    "video_id": row["id"],
                    "content_hash": row["file_hash"],
                    "is_primary": True,
                },
            )

        bind.execute(
            sa.text(
                """
                UPDATE video_storage_objects
                SET is_primary = CASE
                    WHEN storage_backend = :storage_backend AND storage_uri = :storage_uri THEN :true_value
                    ELSE :false_value
                END
                WHERE video_id = :video_id
                """
            ),
            {
                "storage_backend": storage_backend,
                "storage_uri": storage_uri,
                "true_value": True,
                "false_value": False,
                "video_id": row["id"],
            },
        )


def _upsert_transcript_segments(bind) -> None:
    transcript_rows = bind.execute(
        sa.text("SELECT id, content, segments, created_at FROM transcripts")
    ).mappings()
    for row in transcript_rows:
        normalized_segments = _normalize_segments(row["segments"], row["content"])
        existing_rows = {
            existing.segment_id: existing
            for existing in bind.execute(
                sa.text(
                    """
                    SELECT id, segment_id
                    FROM transcript_segments
                    WHERE transcript_id = :transcript_id
                    """
                ),
                {"transcript_id": row["id"]},
            ).mappings()
        }
        seen_segment_ids = set()
        for segment in normalized_segments:
            seen_segment_ids.add(segment["segment_id"])
            existing = existing_rows.get(segment["segment_id"])
            params = {
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
            if existing is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO transcript_segments
                            (transcript_id, segment_id, segment_index, start_time, end_time, text, speaker, created_at, updated_at)
                        VALUES
                            (:transcript_id, :segment_id, :segment_index, :start_time, :end_time, :text, :speaker, :created_at, :updated_at)
                        """
                    ),
                    params,
                )
                continue

            bind.execute(
                sa.text(
                    """
                    UPDATE transcript_segments
                    SET segment_index = :segment_index,
                        start_time = :start_time,
                        end_time = :end_time,
                        text = :text,
                        speaker = :speaker
                    WHERE id = :id
                    """
                ),
                {**params, "id": existing["id"]},
            )

        stale_ids = [existing["id"] for segment_id, existing in existing_rows.items() if segment_id not in seen_segment_ids]
        for stale_id in stale_ids:
            bind.execute(
                sa.text("DELETE FROM transcript_segments WHERE id = :id"),
                {"id": stale_id},
            )


def _upsert_transcript_speakers(bind) -> None:
    transcript_rows = bind.execute(
        sa.text("SELECT id, content, segments, speaker_aliases, created_at FROM transcripts")
    ).mappings()
    for row in transcript_rows:
        normalized_aliases = _normalize_speaker_aliases(row["speaker_aliases"])
        desired_keys = set(normalized_aliases.keys())
        for segment in _normalize_segments(row["segments"], row["content"]):
            speaker = segment.get("speaker")
            if speaker:
                desired_keys.add(speaker)

        desired_speakers = {
            speaker_key: normalized_aliases.get(speaker_key, speaker_key)
            for speaker_key in sorted(speaker_key for speaker_key in desired_keys if speaker_key)
        }
        existing_rows = {
            existing.speaker_key: existing
            for existing in bind.execute(
                sa.text(
                    """
                    SELECT id, speaker_key
                    FROM speakers
                    WHERE transcript_id = :transcript_id
                    """
                ),
                {"transcript_id": row["id"]},
            ).mappings()
        }

        for speaker_key, display_name in desired_speakers.items():
            existing = existing_rows.get(speaker_key)
            params = {
                "transcript_id": row["id"],
                "speaker_key": speaker_key,
                "display_name": display_name,
                "created_at": _coerce_datetime(row["created_at"]),
                "updated_at": _coerce_datetime(row["created_at"]),
            }
            if existing is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO speakers
                            (id, transcript_id, speaker_key, display_name, created_at, updated_at)
                        VALUES
                            (:id, :transcript_id, :speaker_key, :display_name, :created_at, :updated_at)
                        """
                    ),
                    {**params, "id": str(uuid.uuid4())},
                )
                continue

            bind.execute(
                sa.text(
                    """
                    UPDATE speakers
                    SET display_name = :display_name
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"], "display_name": display_name},
            )

        stale_ids = [existing["id"] for key, existing in existing_rows.items() if key not in desired_speakers]
        for stale_id in stale_ids:
            bind.execute(sa.text("DELETE FROM speakers WHERE id = :id"), {"id": stale_id})


def _upsert_translated_segments(bind) -> None:
    translation_rows = bind.execute(
        sa.text("SELECT id, content, segments, created_at FROM translated_transcripts")
    ).mappings()
    for row in translation_rows:
        normalized_segments = _normalize_segments(row["segments"], row["content"])
        existing_rows = {
            existing.segment_id: existing
            for existing in bind.execute(
                sa.text(
                    """
                    SELECT id, segment_id
                    FROM translated_transcript_segments
                    WHERE translated_transcript_id = :translated_transcript_id
                    """
                ),
                {"translated_transcript_id": row["id"]},
            ).mappings()
        }
        seen_segment_ids = set()
        for segment in normalized_segments:
            seen_segment_ids.add(segment["segment_id"])
            existing = existing_rows.get(segment["segment_id"])
            params = {
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
            if existing is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO translated_transcript_segments
                            (translated_transcript_id, segment_id, segment_index, start_time, end_time, text, speaker, created_at, updated_at)
                        VALUES
                            (:translated_transcript_id, :segment_id, :segment_index, :start_time, :end_time, :text, :speaker, :created_at, :updated_at)
                        """
                    ),
                    params,
                )
                continue

            bind.execute(
                sa.text(
                    """
                    UPDATE translated_transcript_segments
                    SET segment_index = :segment_index,
                        start_time = :start_time,
                        end_time = :end_time,
                        text = :text,
                        speaker = :speaker
                    WHERE id = :id
                    """
                ),
                {**params, "id": existing["id"]},
            )

        stale_ids = [existing["id"] for segment_id, existing in existing_rows.items() if segment_id not in seen_segment_ids]
        for stale_id in stale_ids:
            bind.execute(
                sa.text("DELETE FROM translated_transcript_segments WHERE id = :id"),
                {"id": stale_id},
            )


def _upsert_translation_localization(bind) -> None:
    translation_rows = bind.execute(
        sa.text(
            """
            SELECT id, style_guide, glossary_terms, created_at
            FROM translated_transcripts
            """
        )
    ).mappings()
    for row in translation_rows:
        normalized_style_guide = _normalize_style_guide(row["style_guide"])
        existing_style_guide = bind.execute(
            sa.text(
                """
                SELECT id
                FROM style_guides
                WHERE translated_transcript_id = :translated_transcript_id
                """
            ),
            {"translated_transcript_id": row["id"]},
        ).mappings().first()
        if normalized_style_guide:
            if existing_style_guide is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO style_guides
                            (id, translated_transcript_id, content, created_at, updated_at)
                        VALUES
                            (:id, :translated_transcript_id, :content, :created_at, :updated_at)
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "translated_transcript_id": row["id"],
                        "content": normalized_style_guide,
                        "created_at": _coerce_datetime(row["created_at"]),
                        "updated_at": _coerce_datetime(row["created_at"]),
                    },
                )
            else:
                bind.execute(
                    sa.text(
                        """
                        UPDATE style_guides
                        SET content = :content
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": existing_style_guide["id"],
                        "content": normalized_style_guide,
                    },
                )
        elif existing_style_guide is not None:
            bind.execute(
                sa.text("DELETE FROM style_guides WHERE id = :id"),
                {"id": existing_style_guide["id"]},
            )

        normalized_terms = _normalize_glossary_terms(row["glossary_terms"])
        existing_rows = list(
            bind.execute(
                sa.text(
                    """
                    SELECT id
                    FROM glossary_terms
                    WHERE translated_transcript_id = :translated_transcript_id
                    ORDER BY sort_order ASC, created_at ASC
                    """
                ),
                {"translated_transcript_id": row["id"]},
            ).mappings()
        )
        for index, term in enumerate(normalized_terms, start=1):
            existing = existing_rows[index - 1] if index - 1 < len(existing_rows) else None
            params = {
                "translated_transcript_id": row["id"],
                "source_term": term["source_term"],
                "target_term": term["target_term"],
                "notes": term.get("notes"),
                "sort_order": index,
                "created_at": _coerce_datetime(row["created_at"]),
                "updated_at": _coerce_datetime(row["created_at"]),
            }
            if existing is None:
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO glossary_terms
                            (id, translated_transcript_id, source_term, target_term, notes, sort_order, created_at, updated_at)
                        VALUES
                            (:id, :translated_transcript_id, :source_term, :target_term, :notes, :sort_order, :created_at, :updated_at)
                        """
                    ),
                    {**params, "id": str(uuid.uuid4())},
                )
                continue

            bind.execute(
                sa.text(
                    """
                    UPDATE glossary_terms
                    SET source_term = :source_term,
                        target_term = :target_term,
                        notes = :notes,
                        sort_order = :sort_order
                    WHERE id = :id
                    """
                ),
                {**params, "id": existing["id"]},
            )

        for stale_row in existing_rows[len(normalized_terms):]:
            bind.execute(
                sa.text("DELETE FROM glossary_terms WHERE id = :id"),
                {"id": stale_row["id"]},
            )


def _backfill_legacy_snapshot_columns(bind) -> None:
    video_rows = bind.execute(sa.text("SELECT id FROM videos")).mappings()
    for row in video_rows:
        storage_row = bind.execute(
            sa.text(
                """
                SELECT storage_uri
                FROM video_storage_objects
                WHERE video_id = :video_id
                ORDER BY is_primary DESC, created_at DESC
                LIMIT 1
                """
            ),
            {"video_id": row["id"]},
        ).mappings().first()
        bind.execute(
            sa.text("UPDATE videos SET storage_path = :storage_path WHERE id = :id"),
            {
                "id": row["id"],
                "storage_path": storage_row["storage_uri"] if storage_row is not None else None,
            },
        )

    transcript_rows = bind.execute(sa.text("SELECT id FROM transcripts")).mappings()
    for row in transcript_rows:
        segment_rows = bind.execute(
            sa.text(
                """
                SELECT segment_id, start_time, end_time, text, speaker
                FROM transcript_segments
                WHERE transcript_id = :transcript_id
                ORDER BY segment_index ASC, segment_id ASC
                """
            ),
            {"transcript_id": row["id"]},
        ).mappings()
        speaker_rows = bind.execute(
            sa.text(
                """
                SELECT speaker_key, display_name
                FROM speakers
                WHERE transcript_id = :transcript_id
                ORDER BY speaker_key ASC
                """
            ),
            {"transcript_id": row["id"]},
        ).mappings()
        bind.execute(
            sa.text(
                """
                UPDATE transcripts
                SET segments = :segments,
                    speaker_aliases = :speaker_aliases
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "segments": _json_param(
                    [
                        {
                            "id": segment["segment_id"],
                            "start_time": segment["start_time"],
                            "end_time": segment["end_time"],
                            "text": segment["text"],
                            "speaker": segment["speaker"],
                        }
                        for segment in segment_rows
                    ]
                ),
                "speaker_aliases": _json_param(
                    {
                        speaker["speaker_key"]: speaker["display_name"]
                        for speaker in speaker_rows
                    }
                ),
            },
        )

    translated_rows = bind.execute(sa.text("SELECT id FROM translated_transcripts")).mappings()
    for row in translated_rows:
        segment_rows = bind.execute(
            sa.text(
                """
                SELECT segment_id, start_time, end_time, text, speaker
                FROM translated_transcript_segments
                WHERE translated_transcript_id = :translated_transcript_id
                ORDER BY segment_index ASC, segment_id ASC
                """
            ),
            {"translated_transcript_id": row["id"]},
        ).mappings()
        style_guide_row = bind.execute(
            sa.text(
                """
                SELECT content
                FROM style_guides
                WHERE translated_transcript_id = :translated_transcript_id
                """
            ),
            {"translated_transcript_id": row["id"]},
        ).mappings().first()
        glossary_rows = bind.execute(
            sa.text(
                """
                SELECT source_term, target_term, notes
                FROM glossary_terms
                WHERE translated_transcript_id = :translated_transcript_id
                ORDER BY sort_order ASC, created_at ASC
                """
            ),
            {"translated_transcript_id": row["id"]},
        ).mappings()
        bind.execute(
            sa.text(
                """
                UPDATE translated_transcripts
                SET segments = :segments,
                    style_guide = :style_guide,
                    glossary_terms = :glossary_terms
                WHERE id = :id
                """
            ),
            {
                "id": row["id"],
                "segments": _json_param(
                    [
                        {
                            "id": segment["segment_id"],
                            "start_time": segment["start_time"],
                            "end_time": segment["end_time"],
                            "text": segment["text"],
                            "speaker": segment["speaker"],
                        }
                        for segment in segment_rows
                    ]
                ),
                "style_guide": style_guide_row["content"] if style_guide_row is not None else None,
                "glossary_terms": _json_param(
                    [
                        {
                            key: value
                            for key, value in {
                                "source_term": glossary["source_term"],
                                "target_term": glossary["target_term"],
                                "notes": glossary["notes"],
                            }.items()
                            if value not in (None, "")
                        }
                        for glossary in glossary_rows
                    ]
                ),
            },
        )


def upgrade() -> None:
    bind = op.get_bind()
    _backfill_video_storage_objects(bind)
    _upsert_transcript_segments(bind)
    _upsert_transcript_speakers(bind)
    _upsert_translated_segments(bind)
    _upsert_translation_localization(bind)

    with op.batch_alter_table("videos") as batch_op:
        batch_op.drop_constraint("uq_videos_storage_path", type_="unique")
        batch_op.drop_column("storage_path")

    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.drop_column("speaker_aliases")
        batch_op.drop_column("segments")

    with op.batch_alter_table("translated_transcripts") as batch_op:
        batch_op.drop_column("segments")
        batch_op.drop_column("style_guide")
        batch_op.drop_column("glossary_terms")


def downgrade() -> None:
    with op.batch_alter_table("videos") as batch_op:
        batch_op.add_column(sa.Column("storage_path", sa.String(), nullable=True))

    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.add_column(sa.Column("speaker_aliases", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("segments", sa.JSON(), nullable=True))

    with op.batch_alter_table("translated_transcripts") as batch_op:
        batch_op.add_column(sa.Column("segments", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("style_guide", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("glossary_terms", sa.JSON(), nullable=True))

    bind = op.get_bind()
    _backfill_legacy_snapshot_columns(bind)

    with op.batch_alter_table("videos") as batch_op:
        batch_op.create_unique_constraint("uq_videos_storage_path", ["storage_path"])
