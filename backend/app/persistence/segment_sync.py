from __future__ import annotations

import json
from typing import Any, Dict, List

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
from sqlalchemy.orm import Session


def _normalize_segment_id(raw_segment_id: Any, fallback_index: int) -> int:
    try:
        return int(raw_segment_id)
    except (TypeError, ValueError):
        return fallback_index


def normalize_segments(
    raw_segments: Any,
    *,
    fallback_content: str | None = None,
) -> List[Dict[str, Any]]:
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

    normalized_segments: List[Dict[str, Any]] = []
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

        normalized_segments.append(
            {
                "segment_id": segment_id,
                "segment_index": index,
                "start_time": float(segment.get("start_time", 0) or 0),
                "end_time": float(segment.get("end_time", 0) or 0),
                "text": text,
                "speaker": speaker or None,
            }
        )

    return normalized_segments


def build_segments_snapshot_from_normalized_segments(
    normalized_segments: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    return [
        {
            "id": segment["segment_id"],
            "start_time": segment["start_time"],
            "end_time": segment["end_time"],
            "text": segment["text"],
            "speaker": segment["speaker"],
        }
        for segment in normalized_segments
    ]


def build_segments_snapshot_from_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    ordered_rows = sorted(rows, key=lambda row: (row.segment_index, row.segment_id))
    return [
        {
            "id": row.segment_id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "text": row.text,
            "speaker": row.speaker,
        }
        for row in ordered_rows
    ]


def normalize_speaker_aliases(raw_aliases: Any) -> Dict[str, str]:
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


def build_speaker_alias_snapshot(rows: List[Speaker]) -> Dict[str, str]:
    return {
        row.speaker_key: row.display_name
        for row in sorted(rows, key=lambda row: row.speaker_key)
    }


def normalize_style_guide(raw_style_guide: Any) -> str | None:
    if raw_style_guide is None:
        return None

    style_guide = str(raw_style_guide).strip()
    return style_guide or None


def normalize_glossary_terms(raw_terms: Any) -> List[Dict[str, str]]:
    normalized_terms: List[Dict[str, str]] = []
    for index, raw_term in enumerate(raw_terms or [], start=1):
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


def build_glossary_terms_snapshot(rows: List[GlossaryTerm]) -> List[Dict[str, str]]:
    ordered_rows = sorted(rows, key=lambda row: (row.sort_order, row.created_at))
    snapshot: List[Dict[str, str]] = []
    for row in ordered_rows:
        term = {
            "source_term": row.source_term,
            "target_term": row.target_term,
        }
        if row.notes:
            term["notes"] = row.notes
        snapshot.append(term)
    return snapshot


def sync_transcript_segment_rows(db: Session, transcript: Transcript) -> None:
    normalized_segments = normalize_segments(
        transcript.segments,
        fallback_content=transcript.content,
    )

    db.query(TranscriptSegmentRow).filter(TranscriptSegmentRow.transcript_id == transcript.id).delete()

    rows = [
        TranscriptSegmentRow(transcript_id=str(transcript.id), **segment)
        for segment in normalized_segments
    ]
    if rows:
        db.add_all(rows)
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

    db.query(TranslatedTranscriptSegmentRow).filter(
        TranslatedTranscriptSegmentRow.translated_transcript_id == translated_transcript.id
    ).delete()

    rows = [
        TranslatedTranscriptSegmentRow(
            translated_transcript_id=str(translated_transcript.id),
            **segment,
        )
        for segment in normalized_segments
    ]
    if rows:
        db.add_all(rows)
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

    db.query(Speaker).filter(Speaker.transcript_id == transcript.id).delete()
    speaker_rows = [
        Speaker(
            transcript_id=str(transcript.id),
            speaker_key=speaker_key,
            display_name=normalized_aliases.get(speaker_key, speaker_key),
        )
        for speaker_key in sorted(speaker_key for speaker_key in speaker_keys if speaker_key)
    ]
    if speaker_rows:
        db.add_all(speaker_rows)

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
    db.query(GlossaryTerm).filter(
        GlossaryTerm.translated_transcript_id == translated_transcript.id
    ).delete()
    glossary_rows = [
        GlossaryTerm(
            translated_transcript_id=str(translated_transcript.id),
            source_term=term["source_term"],
            target_term=term["target_term"],
            notes=term.get("notes"),
            sort_order=index,
        )
        for index, term in enumerate(normalized_terms, start=1)
    ]
    if glossary_rows:
        db.add_all(glossary_rows)

    translated_transcript.glossary_terms = build_glossary_terms_snapshot(glossary_rows)
    db.flush()


def sync_video_storage_objects(db: Session, video: Video) -> None:
    if not video.storage_path:
        return

    normalized_storage_path = str(video.storage_path)
    existing_object = (
        db.query(VideoStorageObject)
        .filter(VideoStorageObject.storage_backend == "local_fs")
        .filter(VideoStorageObject.storage_uri == normalized_storage_path)
        .first()
    )
    if not existing_object:
        existing_object = VideoStorageObject(
            video_id=str(video.id),
            storage_backend="local_fs",
            storage_uri=normalized_storage_path,
        )
        db.add(existing_object)

    db.query(VideoStorageObject).filter(VideoStorageObject.video_id == video.id).update(
        {VideoStorageObject.is_primary: False}
    )
    existing_object.video_id = str(video.id)
    existing_object.is_primary = True
    existing_object.content_hash = video.file_hash
    db.flush()


def _serialize_summary_variant_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    return json.dumps(content, ensure_ascii=False, indent=2)


def sync_summary_variants(
    db: Session,
    summary: Summary,
    *,
    variants: Dict[str, Any] | None = None,
) -> None:
    normalized_variants: Dict[str, str] = {"default": summary.content}
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
