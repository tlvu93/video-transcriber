from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.app.domain.canonical_metadata import (
    build_segments_snapshot_from_rows,
    normalize_segments,
)
from backend.app.persistence.models import Transcript, TranscriptSegmentRow, TranscriptSegmentSearch, Video
from sqlalchemy import Float, func, or_
from sqlalchemy.orm import Session

def _build_search_payloads(transcript: Transcript, db: Session) -> List[Dict[str, Any]]:
    segment_rows = list(transcript.segment_rows or [])
    if not segment_rows:
        segment_rows = (
            db.query(TranscriptSegmentRow)
            .filter(TranscriptSegmentRow.transcript_id == transcript.id)
            .order_by(TranscriptSegmentRow.segment_index.asc())
            .all()
        )

    segments = (
        build_segments_snapshot_from_rows(segment_rows)
        if segment_rows
        else normalize_segments(
            transcript.segments,
            fallback_content=transcript.content,
        )
    )

    return [
        {
            "transcript_id": str(transcript.id),
            "video_id": str(transcript.video_id) if transcript.video_id else None,
            "segment_id": segment["segment_id"] if "segment_id" in segment else segment["id"],
            "start_time": segment["start_time"],
            "end_time": segment["end_time"],
            "text": segment["text"],
            "speaker": segment.get("speaker"),
        }
        for segment in segments
    ]


def sync_transcript_search_rows(db: Session, transcript: Transcript) -> None:
    """Refresh the read model rows for a transcript."""
    existing_rows = {
        row.segment_id: row
        for row in (
            db.query(TranscriptSegmentSearch)
            .filter(TranscriptSegmentSearch.transcript_id == transcript.id)
            .all()
        )
    }
    seen_segment_ids: set[int] = set()
    for payload in _build_search_payloads(transcript, db):
        segment_id = payload["segment_id"]
        seen_segment_ids.add(segment_id)
        existing_row = existing_rows.get(segment_id)
        if existing_row is None:
            db.add(TranscriptSegmentSearch(**payload))
            continue

        existing_row.video_id = payload["video_id"]
        existing_row.start_time = payload["start_time"]
        existing_row.end_time = payload["end_time"]
        existing_row.text = payload["text"]
        existing_row.speaker = payload["speaker"]

    for segment_id, existing_row in existing_rows.items():
        if segment_id not in seen_segment_ids:
            db.delete(existing_row)
    db.flush()


def rebuild_all_transcript_search_rows(db: Session) -> None:
    """Rebuild the entire search projection from transcript source data."""
    db.query(TranscriptSegmentSearch).delete()
    transcripts = db.query(Transcript).all()
    for transcript in transcripts:
        rows = _build_search_payloads(transcript, db)
        if rows:
            db.add_all(TranscriptSegmentSearch(**row) for row in rows)
    db.commit()


def search_transcript_segments(
    db: Session,
    query: str,
    *,
    language_code: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    review_status: Optional[str] = None,
    speaker: Optional[str] = None,
    video_id: Optional[str] = None,
    video_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Search across indexed transcript segments."""
    normalized_query = query.strip()
    normalized_language_code = (language_code or "").strip().lower()
    normalized_review_status = (review_status or "").strip().lower()
    normalized_speaker = (speaker or "").strip().lower()
    normalized_video_title = (video_title or "").strip().lower()
    normalized_video_id = (video_id or "").strip()

    has_structured_filters = any(
        [
            normalized_language_code,
            normalized_review_status,
            normalized_speaker,
            normalized_video_id,
            normalized_video_title,
        ]
    )
    if len(normalized_query) == 1 and not has_structured_filters:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}
    if not normalized_query and not has_structured_filters:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}

    search_vector = func.to_tsvector("simple", TranscriptSegmentSearch.text)
    ts_query = (
        func.websearch_to_tsquery("simple", normalized_query)
        if len(normalized_query) >= 2
        else None
    )
    fts_rank = (
        func.ts_rank_cd(search_vector, ts_query)
        if ts_query is not None
        else func.cast(0.0, Float)
    )
    trigram_similarity = (
        func.similarity(TranscriptSegmentSearch.text, normalized_query)
        if normalized_query
        else func.cast(0.0, Float)
    )
    filters = []
    if ts_query is not None:
        filters.append(
            or_(
                search_vector.op("@@")(ts_query),
                trigram_similarity >= 0.2,
            )
        )
    if normalized_video_id:
        filters.append(TranscriptSegmentSearch.video_id == normalized_video_id)
    if normalized_language_code:
        filters.append(func.lower(func.coalesce(Transcript.language_code, "")) == normalized_language_code)
    if normalized_review_status:
        filters.append(func.lower(func.coalesce(Transcript.review_status, "")) == normalized_review_status)
    if normalized_speaker:
        filters.append(func.lower(func.coalesce(TranscriptSegmentSearch.speaker, "")).like(f"%{normalized_speaker}%"))
    if normalized_video_title:
        filters.append(func.lower(func.coalesce(Video.filename, "")).like(f"%{normalized_video_title}%"))

    total = (
        db.query(func.count(TranscriptSegmentSearch.id))
        .join(Transcript, TranscriptSegmentSearch.transcript_id == Transcript.id)
        .outerjoin(Video, TranscriptSegmentSearch.video_id == Video.id)
        .filter(*filters)
        .scalar()
        or 0
    )

    rows = (
        db.query(
            TranscriptSegmentSearch,
            Video.filename,
            Transcript.language_code,
            Transcript.review_status,
            fts_rank.label("fts_rank"),
            trigram_similarity.label("similarity"),
        )
        .join(Transcript, TranscriptSegmentSearch.transcript_id == Transcript.id)
        .outerjoin(Video, TranscriptSegmentSearch.video_id == Video.id)
        .filter(*filters)
        .order_by(
            fts_rank.desc(),
            trigram_similarity.desc(),
            TranscriptSegmentSearch.updated_at.desc(),
            TranscriptSegmentSearch.id.desc(),
        )
        .limit(limit)
        .offset(offset)
        .all()
    )

    return {
        "items": [
            {
                "video_id": row.video_id,
                "video_title": filename or "Unknown Video",
                "transcript_id": row.transcript_id,
                "segment_id": row.segment_id,
                "start_time": row.start_time,
                "end_time": row.end_time,
                "text": row.text,
                "language_code": language or None,
                "review_status": review or None,
                "speaker": row.speaker or "Unknown",
            }
            for row, filename, language, review, _fts_rank, _similarity in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }
