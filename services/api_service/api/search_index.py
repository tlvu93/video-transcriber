from __future__ import annotations

from typing import Any, Dict, List

from api.models import Transcript, TranscriptSegmentSearch, Video
from sqlalchemy.orm import Session


def _normalize_segment_id(raw_segment_id: Any, fallback_index: int) -> int:
    try:
        return int(raw_segment_id)
    except (TypeError, ValueError):
        return fallback_index


def _build_search_rows(transcript: Transcript) -> List[TranscriptSegmentSearch]:
    rows: List[TranscriptSegmentSearch] = []
    segments = transcript.segments or []

    if not segments and transcript.content:
        segments = [
            {
                "id": 1,
                "start_time": 0,
                "end_time": 0,
                "text": transcript.content,
                "speaker": None,
            }
        ]

    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue

        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        rows.append(
            TranscriptSegmentSearch(
                transcript_id=str(transcript.id),
                video_id=str(transcript.video_id) if transcript.video_id else None,
                segment_id=_normalize_segment_id(segment.get("id"), index),
                start_time=float(segment.get("start_time", 0) or 0),
                end_time=float(segment.get("end_time", 0) or 0),
                text=text,
                speaker=str(segment.get("speaker")) if segment.get("speaker") else None,
            )
        )

    return rows


def sync_transcript_search_rows(db: Session, transcript: Transcript) -> None:
    """Refresh the read model rows for a transcript."""
    db.query(TranscriptSegmentSearch).filter(
        TranscriptSegmentSearch.transcript_id == transcript.id
    ).delete()

    rows = _build_search_rows(transcript)
    if rows:
        db.add_all(rows)

    db.commit()


def rebuild_all_transcript_search_rows(db: Session) -> None:
    """Rebuild the entire search projection from transcript source data."""
    db.query(TranscriptSegmentSearch).delete()
    transcripts = db.query(Transcript).all()
    for transcript in transcripts:
        rows = _build_search_rows(transcript)
        if rows:
            db.add_all(rows)
    db.commit()


def search_transcript_segments(db: Session, query: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Search across indexed transcript segments."""
    if not query or len(query) < 2:
        return []

    rows = (
        db.query(TranscriptSegmentSearch, Video.filename)
        .outerjoin(Video, TranscriptSegmentSearch.video_id == Video.id)
        .filter(TranscriptSegmentSearch.text.ilike(f"%{query}%"))
        .order_by(TranscriptSegmentSearch.updated_at.desc(), TranscriptSegmentSearch.id.desc())
        .limit(limit)
        .all()
    )

    return [
        {
            "video_id": row.video_id,
            "video_title": filename or "Unknown Video",
            "transcript_id": row.transcript_id,
            "segment_id": row.segment_id,
            "start_time": row.start_time,
            "end_time": row.end_time,
            "text": row.text,
            "speaker": row.speaker or "Unknown",
        }
        for row, filename in rows
    ]
