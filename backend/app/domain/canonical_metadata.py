from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


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


def build_segments_snapshot_from_rows(rows: Iterable[Any]) -> List[Dict[str, Any]]:
    ordered_rows = sorted(
        rows,
        key=lambda row: (getattr(row, "segment_index", 0), getattr(row, "segment_id", 0)),
    )
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


def build_speaker_alias_snapshot(rows: Iterable[Any]) -> Dict[str, str]:
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


def build_glossary_terms_snapshot(rows: Iterable[Any]) -> List[Dict[str, str]]:
    ordered_rows = sorted(
        rows,
        key=lambda row: (
            getattr(row, "sort_order", 0),
            getattr(row, "created_at", None) or datetime.min,
        ),
    )
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


def resolve_primary_storage_uri(
    storage_objects: Iterable[Any],
    *,
    fallback_uri: Optional[str] = None,
) -> Optional[str]:
    storage_object_list = list(storage_objects)
    for row in storage_object_list:
        if getattr(row, "is_primary", False):
            return row.storage_uri
    if storage_object_list:
        return storage_object_list[0].storage_uri
    return fallback_uri
