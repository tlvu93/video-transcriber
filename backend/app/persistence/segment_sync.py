from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from backend.app.domain.canonical_metadata import (
    build_glossary_terms_snapshot,
    build_segments_snapshot_from_normalized_segments,
    build_speaker_alias_snapshot,
    normalize_glossary_terms,
    normalize_segments,
    normalize_speaker_aliases,
    normalize_style_guide,
    resolve_primary_storage_uri,
)
from backend.app.persistence.models import (
    GlossaryTerm,
    Speaker,
    StyleGuide,
    Summary,
    SummaryVariant,
    Transcript,
    TranscriptSegmentRow,
    TranslatedTranscript,
    TranslatedTranscriptSegmentRow,
    Video,
    VideoStorageObject,
)


def sync_transcript_segment_rows(db: Session, transcript: Transcript) -> None:
    normalized_segments = normalize_segments(
        transcript.segments,
        fallback_content=transcript.content,
    )
    existing_rows = {
        row.segment_id: row
        for row in (
            db.query(TranscriptSegmentRow)
            .filter(TranscriptSegmentRow.transcript_id == transcript.id)
            .all()
        )
    }
    seen_segment_ids: set[int] = set()

    for segment in normalized_segments:
        segment_id = segment["segment_id"]
        seen_segment_ids.add(segment_id)
        existing_row = existing_rows.get(segment_id)
        if existing_row is None:
            db.add(
                TranscriptSegmentRow(
                    transcript_id=str(transcript.id),
                    **segment,
                )
            )
            continue

        existing_row.segment_index = segment["segment_index"]
        existing_row.start_time = segment["start_time"]
        existing_row.end_time = segment["end_time"]
        existing_row.text = segment["text"]
        existing_row.speaker = segment["speaker"]

    for segment_id, existing_row in existing_rows.items():
        if segment_id not in seen_segment_ids:
            db.delete(existing_row)

    transcript.segments = build_segments_snapshot_from_normalized_segments(normalized_segments)
    db.flush()


def sync_translated_transcript_segment_rows(
    db: Session,
    translated_transcript: TranslatedTranscript,
) -> None:
    normalized_segments = normalize_segments(
        translated_transcript.segments,
        fallback_content=translated_transcript.content,
    )

    existing_rows = {
        row.segment_id: row
        for row in (
            db.query(TranslatedTranscriptSegmentRow)
            .filter(
                TranslatedTranscriptSegmentRow.translated_transcript_id == translated_transcript.id
            )
            .all()
        )
    }
    seen_segment_ids: set[int] = set()

    for segment in normalized_segments:
        segment_id = segment["segment_id"]
        seen_segment_ids.add(segment_id)
        existing_row = existing_rows.get(segment_id)
        if existing_row is None:
            db.add(
                TranslatedTranscriptSegmentRow(
                    translated_transcript_id=str(translated_transcript.id),
                    **segment,
                )
            )
            continue

        existing_row.segment_index = segment["segment_index"]
        existing_row.start_time = segment["start_time"]
        existing_row.end_time = segment["end_time"]
        existing_row.text = segment["text"]
        existing_row.speaker = segment["speaker"]

    for segment_id, existing_row in existing_rows.items():
        if segment_id not in seen_segment_ids:
            db.delete(existing_row)

    translated_transcript.segments = build_segments_snapshot_from_normalized_segments(normalized_segments)
    db.flush()


def sync_transcript_speaker_rows(db: Session, transcript: Transcript) -> None:
    normalized_aliases = normalize_speaker_aliases(transcript.speaker_aliases)
    speaker_keys = set(normalized_aliases.keys())
    for segment in build_segments_snapshot_from_normalized_segments(
        normalize_segments(transcript.segments, fallback_content=transcript.content)
    ):
        speaker = segment.get("speaker")
        if speaker:
            speaker_keys.add(str(speaker).strip())

    desired_speakers = {
        speaker_key: normalized_aliases.get(speaker_key, speaker_key)
        for speaker_key in sorted(speaker_key for speaker_key in speaker_keys if speaker_key)
    }
    existing_rows = {
        row.speaker_key: row
        for row in (
            db.query(Speaker)
            .filter(Speaker.transcript_id == transcript.id)
            .all()
        )
    }

    for speaker_key, display_name in desired_speakers.items():
        existing_row = existing_rows.get(speaker_key)
        if existing_row is None:
            db.add(
                Speaker(
                    transcript_id=str(transcript.id),
                    speaker_key=speaker_key,
                    display_name=display_name,
                )
            )
            continue
        existing_row.display_name = display_name

    for speaker_key, existing_row in existing_rows.items():
        if speaker_key not in desired_speakers:
            db.delete(existing_row)

    speaker_rows = (
        db.query(Speaker)
        .filter(Speaker.transcript_id == transcript.id)
        .order_by(Speaker.speaker_key.asc())
        .all()
    )
    transcript.speaker_aliases = build_speaker_alias_snapshot(speaker_rows)
    db.flush()


def sync_translated_transcript_localization_rows(
    db: Session,
    translated_transcript: TranslatedTranscript,
) -> None:
    normalized_style_guide = normalize_style_guide(translated_transcript.style_guide)
    existing_style_guide = (
        db.query(StyleGuide)
        .filter(StyleGuide.translated_transcript_id == translated_transcript.id)
        .first()
    )
    if normalized_style_guide:
        if existing_style_guide:
            existing_style_guide.content = normalized_style_guide
        else:
            db.add(
                StyleGuide(
                    translated_transcript_id=str(translated_transcript.id),
                    content=normalized_style_guide,
                )
            )
    elif existing_style_guide:
        db.delete(existing_style_guide)
    translated_transcript.style_guide = normalized_style_guide

    normalized_terms = normalize_glossary_terms(translated_transcript.glossary_terms)
    existing_rows = (
        db.query(GlossaryTerm)
        .filter(GlossaryTerm.translated_transcript_id == translated_transcript.id)
        .order_by(GlossaryTerm.sort_order.asc(), GlossaryTerm.created_at.asc())
        .all()
    )

    for index, term in enumerate(normalized_terms, start=1):
        existing_row = existing_rows[index - 1] if index - 1 < len(existing_rows) else None
        if existing_row is None:
            db.add(
                GlossaryTerm(
                    translated_transcript_id=str(translated_transcript.id),
                    source_term=term["source_term"],
                    target_term=term["target_term"],
                    notes=term.get("notes"),
                    sort_order=index,
                )
            )
            continue

        existing_row.sort_order = index
        existing_row.source_term = term["source_term"]
        existing_row.target_term = term["target_term"]
        existing_row.notes = term.get("notes")

    for stale_row in existing_rows[len(normalized_terms) :]:
        db.delete(stale_row)

    glossary_rows = (
        db.query(GlossaryTerm)
        .filter(GlossaryTerm.translated_transcript_id == translated_transcript.id)
        .order_by(GlossaryTerm.sort_order.asc(), GlossaryTerm.created_at.asc())
        .all()
    )
    translated_transcript.glossary_terms = build_glossary_terms_snapshot(glossary_rows)
    db.flush()


def sync_video_storage_objects(db: Session, video: Video) -> None:
    if not video.storage_path:
        return

    normalized_storage_path = str(video.storage_path)
    parsed_storage_uri = urlparse(normalized_storage_path)
    storage_backend_name = "s3_compatible" if parsed_storage_uri.scheme == "s3" else "local_fs"
    existing_object = (
        db.query(VideoStorageObject)
        .filter(VideoStorageObject.storage_backend == storage_backend_name)
        .filter(VideoStorageObject.storage_uri == normalized_storage_path)
        .first()
    )
    if not existing_object:
        existing_object = VideoStorageObject(
            video_id=str(video.id),
            storage_backend=storage_backend_name,
            storage_uri=normalized_storage_path,
        )
        db.add(existing_object)

    db.query(VideoStorageObject).filter(VideoStorageObject.video_id == video.id).update(
        {VideoStorageObject.is_primary: False}
    )
    existing_object.video_id = str(video.id)
    existing_object.is_primary = True
    existing_object.content_hash = video.file_hash
    video.storage_path = resolve_primary_storage_uri([existing_object]) or existing_object.storage_uri
    db.flush()


def _serialize_summary_variant_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    return json.dumps(content, ensure_ascii=False, indent=2)


def sync_summary_variants(
    db: Session,
    summary: Summary,
    *,
    variants: dict[str, Any] | None = None,
) -> None:
    normalized_variants: dict[str, str] = {"default": summary.content}
    for variant_type, content in (variants or {}).items():
        normalized_type = str(variant_type or "").strip()
        if not normalized_type or content is None:
            continue

        serialized_content = _serialize_summary_variant_content(content)
        if serialized_content:
            normalized_variants[normalized_type] = serialized_content

    existing_variants = {
        variant.variant_type: variant
        for variant in (
            db.query(SummaryVariant)
            .filter(SummaryVariant.summary_id == summary.id)
            .all()
        )
    }

    for variant_type, content in normalized_variants.items():
        existing_variant = existing_variants.get(variant_type)
        if existing_variant:
            existing_variant.content = content
        else:
            db.add(
                SummaryVariant(
                    summary_id=str(summary.id),
                    variant_type=variant_type,
                    content=content,
                )
            )

    for variant_type, existing_variant in existing_variants.items():
        if variant_type not in normalized_variants:
            db.delete(existing_variant)

    db.flush()
