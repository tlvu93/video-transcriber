from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.domain.canonical_metadata import (
    build_glossary_terms_snapshot,
    build_segments_snapshot_from_rows,
    build_speaker_alias_snapshot,
    normalize_glossary_terms,
    normalize_speaker_aliases,
    normalize_style_guide as normalize_translation_style_guide,
    resolve_primary_storage_uri,
)
from backend.app.persistence.search_index import sync_transcript_search_rows
from backend.app.persistence.segment_sync import (
    sync_summary_variants,
    sync_transcript_segment_rows,
    sync_transcript_speaker_rows,
    sync_translated_transcript_segment_rows,
    sync_translated_transcript_localization_rows,
    sync_video_storage_objects,
)
from backend.app.domain.events import (
    EVENT_SUMMARY_CREATED,
    EVENT_TRANSCRIPT_UPDATED,
    EVENT_TRANSCRIPTION_CREATED,
    EVENT_TRANSLATED_TRANSCRIPT_UPDATED,
    EVENT_TRANSLATION_CREATED,
    EVENT_VIDEO_CREATED,
    EVENT_VIDEO_UPDATED,
    publish_live_update_sync,
)
from backend.app.persistence.database import SessionLocal
from backend.app.persistence.models import (
    Summary,
    Transcript,
    TranscriptRevision,
    TranslatedTranscript,
    Video,
    VideoStorageObject,
)
from backend.app.runtime.storage import get_storage_backend


logger = logging.getLogger("backend.domain.records")
storage_backend = get_storage_backend()


def serialize_video(video: Video) -> Dict[str, Any]:
    return {
        "id": str(video.id),
        "filename": video.filename,
        "status": video.status,
        "created_at": video.created_at,
        "file_hash": video.file_hash,
        "video_metadata": video.video_metadata,
        "storage_path": resolve_primary_storage_uri(video.storage_objects or [], fallback_uri=video.storage_path),
    }


def serialize_transcript(transcript: Transcript) -> Dict[str, Any]:
    speaker_aliases = (
        build_speaker_alias_snapshot(list(transcript.speakers))
        if transcript.speakers
        else normalize_speaker_aliases(transcript.speaker_aliases)
    )
    segments = (
        build_segments_snapshot_from_rows(list(transcript.segment_rows))
        if transcript.segment_rows
        else transcript.segments
    )
    return {
        "id": str(transcript.id),
        "video_id": str(transcript.video_id) if transcript.video_id else None,
        "source_type": transcript.source_type,
        "content": transcript.content,
        "format": transcript.format,
        "status": transcript.status,
        "language_code": transcript.language_code,
        "speaker_aliases": speaker_aliases,
        "review_status": transcript.review_status,
        "review_assignee": transcript.review_assignee,
        "created_at": transcript.created_at,
        "segments": segments,
    }


def serialize_summary(summary: Summary) -> Dict[str, Any]:
    variants = {
        variant.variant_type: variant.content
        for variant in (summary.variants or [])
    }
    return {
        "id": str(summary.id),
        "transcript_id": str(summary.transcript_id),
        "content": summary.content,
        "content_profile": summary.content_profile,
        "summary_metadata": summary.summary_metadata or {},
        "status": summary.status,
        "created_at": summary.created_at,
        "variants": variants,
    }


def serialize_translated_transcript(translated_transcript: TranslatedTranscript) -> Dict[str, Any]:
    segments = (
        build_segments_snapshot_from_rows(list(translated_transcript.segment_rows))
        if translated_transcript.segment_rows
        else translated_transcript.segments
    )
    glossary_terms = (
        build_glossary_terms_snapshot(list(translated_transcript.glossary_term_rows))
        if translated_transcript.glossary_term_rows
        else translated_transcript.glossary_terms or []
    )
    return {
        "id": str(translated_transcript.id),
        "transcript_id": str(translated_transcript.transcript_id),
        "language": translated_transcript.language,
        "content": translated_transcript.content,
        "segments": segments,
        "style_guide": (
            translated_transcript.style_guide_row.content
            if translated_transcript.style_guide_row is not None
            else normalize_translation_style_guide(translated_transcript.style_guide)
        ),
        "glossary_terms": glossary_terms,
        "qa_metrics": translated_transcript.qa_metrics or {},
        "status": translated_transcript.status,
        "created_at": translated_transcript.created_at,
    }

def create_transcript_revision(db: Session, transcript: Transcript, *, reason: str) -> None:
    if not transcript.id:
        db.flush()

    next_revision_number = (
        db.query(func.max(TranscriptRevision.revision_number))
        .filter(TranscriptRevision.transcript_id == transcript.id)
        .scalar()
        or 0
    ) + 1

    db.add(
        TranscriptRevision(
            transcript_id=str(transcript.id),
            revision_number=int(next_revision_number),
            reason=reason,
            content=transcript.content,
            segments=(
                build_segments_snapshot_from_rows(list(transcript.segment_rows))
                if transcript.segment_rows
                else transcript.segments
            ),
            speaker_aliases=(
                build_speaker_alias_snapshot(list(transcript.speakers))
                if transcript.speakers
                else normalize_speaker_aliases(transcript.speaker_aliases)
            ),
        )
    )


def canonicalize_storage_path(storage_path: Optional[str]) -> Optional[str]:
    return storage_backend.normalize_uri(storage_path)


def resolve_video_storage_path(
    filename: str,
    *,
    storage_path: Optional[str] = None,
) -> str:
    return storage_backend.resolve_video_path(
        filename,
        storage_uri=storage_path,
    )


def merge_video_metadata(
    existing_metadata: Optional[Dict[str, Any]],
    incoming_metadata: Optional[Dict[str, Any]],
    file_hash: Optional[str],
) -> Dict[str, Any]:
    merged_metadata = dict(existing_metadata or {})
    if file_hash:
        merged_metadata["file_hash"] = file_hash
    if incoming_metadata:
        merged_metadata.update(incoming_metadata)
    return merged_metadata


def find_existing_video(
    db: Session,
    *,
    filename: str,
    storage_path: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> tuple[Optional[Video], Optional[str]]:
    if storage_path:
        storage_object = (
            db.query(VideoStorageObject)
            .filter(VideoStorageObject.storage_uri == storage_path)
            .order_by(VideoStorageObject.is_primary.desc(), VideoStorageObject.created_at.desc())
            .first()
        )
        existing_video = storage_object.video if storage_object is not None else None
        if existing_video:
            return existing_video, "storage_path"

    if file_hash:
        existing_video = db.query(Video).filter(Video.file_hash == file_hash).first()
        if existing_video:
            return existing_video, "file_hash"

    if filename and not storage_path and not file_hash:
        existing_video = db.query(Video).filter(Video.filename == filename).first()
        if existing_video:
            return existing_video, "filename"

    return None, None


def get_video(video_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video not found: {video_id}")
        return serialize_video(video)
    finally:
        db.close()


def get_transcript(transcript_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            raise ValueError(f"Transcript not found: {transcript_id}")
        return serialize_transcript(transcript)
    finally:
        db.close()


def update_video_status(video_id: str, status: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        video.status = status
        db.commit()
        db.refresh(video)

        publish_live_update_sync(
            EVENT_VIDEO_UPDATED,
            filename=video.filename,
            status=video.status,
            video_id=str(video.id),
        )
        return serialize_video(video)
    finally:
        db.close()


def update_transcript_status(transcript_id: str, status: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            raise ValueError(f"Transcript not found: {transcript_id}")

        transcript.status = status
        db.commit()
        db.refresh(transcript)

        publish_live_update_sync(
            EVENT_TRANSCRIPT_UPDATED,
            status=transcript.status,
            transcript_id=str(transcript.id),
            video_id=str(transcript.video_id) if transcript.video_id else None,
        )
        return serialize_transcript(transcript)
    finally:
        db.close()


def create_transcript_record(
    video_id: str,
    content: str,
    *,
    segments: Optional[List[Dict[str, Any]]] = None,
    language_code: Optional[str] = None,
    source_type: str = "video",
    format_name: str = "txt",
    status: str = "completed",
    enqueue_summarization: bool = True,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        transcript = Transcript(
            video_id=video_id,
            source_type=source_type,
            content=content,
            format=format_name,
            status=status,
            language_code=language_code,
            speaker_aliases={},
            review_status="draft",
            review_assignee=None,
            segments=segments,
        )
        db.add(transcript)
        db.flush()
        sync_transcript_segment_rows(db, transcript)
        sync_transcript_speaker_rows(db, transcript)
        create_transcript_revision(db, transcript, reason="initial_import")
        sync_transcript_search_rows(db, transcript)
        db.commit()
        db.refresh(transcript)

        publish_live_update_sync(
            EVENT_TRANSCRIPTION_CREATED,
            transcript_id=str(transcript.id),
            video_id=str(transcript.video_id),
        )
        serialized_transcript = serialize_transcript(transcript)
    finally:
        db.close()

    if enqueue_summarization:
        from backend.app.domain.jobs import create_summarization_job_for_transcript

        create_summarization_job_for_transcript(str(serialized_transcript["id"]))

    return serialized_transcript


def create_summary_record(
    transcript_id: str,
    content: str,
    *,
    content_profile: str = "generic",
    summary_metadata: Optional[Dict[str, Any]] = None,
    status: str = "completed",
    variants: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            raise ValueError(f"Transcript not found: {transcript_id}")

        summary = Summary(
            transcript_id=transcript_id,
            content=content,
            content_profile=content_profile,
            summary_metadata=summary_metadata or {},
            status=status,
        )
        db.add(summary)
        db.flush()
        sync_summary_variants(
            db,
            summary,
            variants=variants,
        )
        db.commit()
        db.refresh(summary)

        publish_live_update_sync(
            EVENT_SUMMARY_CREATED,
            summary_id=str(summary.id),
            transcript_id=str(summary.transcript_id),
        )
        return serialize_summary(summary)
    finally:
        db.close()


def create_or_update_translated_transcript(
    transcript_id: str,
    language: str,
    content: str,
    *,
    segments: Optional[List[Dict[str, Any]]] = None,
    style_guide: Optional[str] = None,
    glossary_terms: Optional[List[Dict[str, Any]]] = None,
    qa_metrics: Optional[Dict[str, Any]] = None,
    status: str = "completed",
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            raise ValueError(f"Transcript not found: {transcript_id}")

        translated_transcript = (
            db.query(TranslatedTranscript)
            .filter(TranslatedTranscript.transcript_id == transcript_id)
            .filter(TranslatedTranscript.language == language)
            .order_by(TranslatedTranscript.created_at.desc())
            .first()
        )

        is_existing_translation = translated_transcript is not None
        normalized_style_guide = normalize_translation_style_guide(style_guide)
        normalized_glossary_terms = normalize_glossary_terms(glossary_terms)

        if translated_transcript:
            translated_transcript.content = content
            translated_transcript.segments = segments
            translated_transcript.style_guide = normalized_style_guide
            translated_transcript.glossary_terms = normalized_glossary_terms
            translated_transcript.qa_metrics = qa_metrics or {}
            translated_transcript.status = status
        else:
            translated_transcript = TranslatedTranscript(
                transcript_id=transcript_id,
                language=language,
                content=content,
                segments=segments,
                style_guide=normalized_style_guide,
                glossary_terms=normalized_glossary_terms,
                qa_metrics=qa_metrics or {},
                status=status,
            )
            db.add(translated_transcript)

        db.flush()
        sync_translated_transcript_segment_rows(db, translated_transcript)
        sync_translated_transcript_localization_rows(db, translated_transcript)
        db.commit()
        db.refresh(translated_transcript)

        if is_existing_translation:
            publish_live_update_sync(
                EVENT_TRANSLATED_TRANSCRIPT_UPDATED,
                language=translated_transcript.language,
                transcript_id=str(translated_transcript.transcript_id),
                translated_transcript_id=str(translated_transcript.id),
            )
        else:
            publish_live_update_sync(
                EVENT_TRANSLATION_CREATED,
                language=translated_transcript.language,
                transcript_id=str(translated_transcript.transcript_id),
                translated_transcript_id=str(translated_transcript.id),
            )

        return serialize_translated_transcript(translated_transcript)
    finally:
        db.close()


def register_watched_video(
    *,
    filename: str,
    file_hash: Optional[str] = None,
    storage_path: Optional[str] = None,
    video_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        requested_storage_path = canonicalize_storage_path(storage_path)
        resolved_file_path = resolve_video_storage_path(
            filename,
            storage_path=requested_storage_path,
        )
        canonical_storage_path = requested_storage_path or canonicalize_storage_path(
            resolved_file_path
        )

        existing_video, match_reason = find_existing_video(
            db,
            filename=filename,
            storage_path=canonical_storage_path,
            file_hash=file_hash,
        )

        if existing_video:
            existing_storage_path = canonicalize_storage_path(existing_video.storage_path)
            if existing_storage_path == canonical_storage_path:
                return {
                    "video": serialize_video(existing_video),
                    "job": None,
                    "created": False,
                    "match_reason": match_reason,
                }

            existing_video.filename = filename
            existing_video.file_hash = file_hash or existing_video.file_hash
            existing_video.storage_path = canonical_storage_path
            existing_video.video_metadata = merge_video_metadata(
                existing_video.video_metadata,
                video_metadata,
                file_hash,
            )
            sync_video_storage_objects(db, existing_video)
            db.commit()
            db.refresh(existing_video)

            publish_live_update_sync(
                EVENT_VIDEO_UPDATED,
                filename=existing_video.filename,
                status=existing_video.status,
                video_id=str(existing_video.id),
            )
            return {
                "video": serialize_video(existing_video),
                "job": None,
                "created": False,
                "match_reason": match_reason,
            }

        video = Video(
            filename=filename,
            file_hash=file_hash,
            storage_path=canonical_storage_path,
            status="pending",
            video_metadata=merge_video_metadata(None, video_metadata, file_hash),
        )
        db.add(video)
        db.flush()
        sync_video_storage_objects(db, video)
        db.commit()
        db.refresh(video)

        publish_live_update_sync(
            EVENT_VIDEO_CREATED,
            filename=video.filename,
            status=video.status,
            video_id=str(video.id),
        )
        video_payload = serialize_video(video)
    finally:
        db.close()

    from backend.app.domain.jobs import create_transcription_job_for_video

    return {
        "video": video_payload,
        "job": create_transcription_job_for_video(str(video_payload["id"])),
        "created": True,
        "match_reason": None,
    }
