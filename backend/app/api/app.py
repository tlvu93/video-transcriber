from __future__ import annotations

import logging
import json
import io
import os
import re
import shutil
import stat
import tempfile
import time
import zipfile
from datetime import datetime
from datetime import timedelta
from typing import Any, Dict, Generic, List, Literal, Optional, TypeVar
from uuid import uuid4

from backend.app.api.live_updates import build_live_update_filters, live_update_manager
from backend.app.domain.jobs import (
    JobLeaseOwnershipError,
    claim_next_summarization_job,
    claim_next_transcription_job,
    claim_next_translation_job,
    complete_legacy_job,
    create_summarization_job_for_transcript,
    create_transcription_job_for_video,
    create_translation_job_for_transcript,
    heartbeat_legacy_job,
    request_job_cancellation,
    retry_job,
    retry_legacy_job,
    fail_legacy_job,
)
from backend.app.persistence.database import engine, get_db
from backend.app.persistence.models import (
    JobAttempt,
    SummarizationJob,
    Summary,
    Transcript,
    TranscriptComment,
    TranscriptRevision,
    TranscriptSegmentSearch,
    TranscriptionJob,
    TranslatedTranscript,
    TranslationJob,
    UnifiedJob,
    Video,
)
from backend.app.persistence.search_index import search_transcript_segments, sync_transcript_search_rows
from backend.app.persistence.segment_sync import (
    build_segments_snapshot_from_rows,
    build_speaker_alias_snapshot,
    sync_summary_variants,
    sync_transcript_segment_rows,
    sync_transcript_speaker_rows,
    sync_translated_transcript_localization_rows,
    sync_translated_transcript_segment_rows,
    sync_video_storage_objects,
)
from backend.app.runtime.config import LIVE_UPDATES_NOTIFY_ENABLED, VIDEO_DIR
from backend.app.runtime.metrics import record_metric_event, summarize_metric_events
from backend.app.runtime.observability import bind_request_id, reset_request_id
from backend.app.runtime.storage import get_storage_backend
from fastapi import (
    BackgroundTasks,
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    WebSocket,
)
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, text
from sqlalchemy.orm import Query as SqlAlchemyQuery
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api")
storage_backend = get_storage_backend()

# Create FastAPI app
app = FastAPI(title="Video Transcriber API")

ItemT = TypeVar("ItemT")

# Ensure directories exist
os.makedirs(VIDEO_DIR, exist_ok=True)

EVENT_VIDEO_UPDATED = "video.updated"
EVENT_TRANSCRIPT_UPDATED = "transcript.updated"
EVENT_TRANSLATED_TRANSCRIPT_UPDATED = "translated_transcript.updated"
EVENT_VIDEO_CREATED = "video.created"
EVENT_TRANSCRIPTION_CREATED = "transcription.created"
EVENT_SUMMARY_CREATED = "summary.created"
EVENT_TRANSLATION_CREATED = "translation.created"
EVENT_JOB_STATUS_CHANGED = "job.status.changed"


@app.middleware("http")
async def add_request_observability(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", "").strip() or str(uuid4())
    request.state.request_id = request_id
    request_context_token = bind_request_id(request_id)
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_seconds = time.perf_counter() - started_at
        record_metric_event(
            "api_request_duration_seconds",
            duration_seconds,
            source="api",
            labels={
                "method": request.method,
                "path": request.url.path,
                "status_code": "500",
            },
        )
        record_metric_event(
            "api_requests_total",
            1,
            source="api",
            labels={
                "method": request.method,
                "path": request.url.path,
                "status_code": "500",
            },
        )
        reset_request_id(request_context_token)
        raise

    duration_seconds = time.perf_counter() - started_at
    status_code = str(response.status_code)
    response.headers["X-Request-ID"] = request_id
    record_metric_event(
        "api_request_duration_seconds",
        duration_seconds,
        source="api",
        labels={
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
        },
    )
    record_metric_event(
        "api_requests_total",
        1,
        source="api",
        labels={
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
        },
    )
    reset_request_id(request_context_token)
    return response


@app.on_event("startup")
async def startup_live_updates() -> None:
    await live_update_manager.start()


@app.on_event("shutdown")
async def shutdown_live_updates() -> None:
    await live_update_manager.stop()


async def publish_live_update(event_type: str, **payload: Any) -> None:
    await live_update_manager.publish(
        {
            "type": event_type,
            **{key: value for key, value in payload.items() if value is not None},
        }
    )


async def publish_job_live_update(
    job_type: str,
    job_id: str,
    status: str,
    *,
    video_id: Optional[str] = None,
    transcript_id: Optional[str] = None,
    worker_id: Optional[str] = None,
    lease_expires_at: Optional[datetime] = None,
) -> None:
    await publish_live_update(
        EVENT_JOB_STATUS_CHANGED,
        job_id=job_id,
        job_type=job_type,
        status=status,
        transcript_id=transcript_id,
        video_id=video_id,
        worker_id=worker_id,
        lease_expires_at=lease_expires_at.isoformat() if lease_expires_at else None,
    )


def get_legacy_job_or_404(
    db: Session,
    *,
    job_type: Literal["summarization", "transcription", "translation"],
    legacy_job_id: str,
) -> TranscriptionJob | SummarizationJob | TranslationJob:
    model_map = {
        "transcription": TranscriptionJob,
        "summarization": SummarizationJob,
        "translation": TranslationJob,
    }
    model = model_map[job_type]
    job = db.query(model).filter(model.id == legacy_job_id).first()
    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"{job_type.title()} job not found: {legacy_job_id}",
        )
    return job


def translate_job_domain_error(error: ValueError) -> HTTPException:
    detail = str(error)
    status_code = 404 if "not found" in detail.lower() else 400
    return HTTPException(status_code=status_code, detail=detail)


def build_video_response(video: Video) -> Dict[str, Any]:
    return {
        "id": str(video.id),
        "filename": video.filename,
        "status": video.status,
        "created_at": video.created_at,
        "file_hash": video.file_hash,
        "video_metadata": video.video_metadata,
        "storage_path": video.storage_path,
    }


def normalize_speaker_aliases(raw_aliases: Optional[Dict[str, Any]]) -> Dict[str, str]:
    normalized: Dict[str, str] = {}
    if not isinstance(raw_aliases, dict):
        return normalized

    for raw_speaker_id, raw_speaker_name in raw_aliases.items():
        speaker_id = str(raw_speaker_id).strip()
        if not speaker_id:
            continue

        speaker_name = str(raw_speaker_name).strip() if raw_speaker_name is not None else ""
        normalized[speaker_id] = speaker_name or speaker_id

    return normalized


def normalize_translation_style_guide(raw_style_guide: Optional[str]) -> Optional[str]:
    if raw_style_guide is None:
        return None

    style_guide = raw_style_guide.strip()
    return style_guide or None


def normalize_glossary_terms(
    raw_terms: Optional[List["TranslationGlossaryTermInput"]],
) -> List[Dict[str, str]]:
    normalized_terms: List[Dict[str, str]] = []
    for raw_term in raw_terms or []:
        source_term = raw_term.source_term.strip()
        target_term = raw_term.target_term.strip()
        if not source_term or not target_term:
            continue

        normalized_term = {
            "source_term": source_term,
            "target_term": target_term,
        }
        if raw_term.notes and raw_term.notes.strip():
            normalized_term["notes"] = raw_term.notes.strip()

        normalized_terms.append(normalized_term)

    return normalized_terms


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


def build_export_segments(
    content: str,
    segments: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    normalized_segments = [segment for segment in segments or [] if isinstance(segment, dict)]
    if normalized_segments:
        return normalized_segments

    if not content:
        return []

    return [
        {
            "id": 1,
            "start_time": 0,
            "end_time": 0,
            "text": content,
            "speaker": None,
        }
    ]


def format_export_timestamp(seconds: float, *, separator: str) -> str:
    safe_seconds = max(float(seconds or 0), 0)
    whole_seconds = int(safe_seconds)
    milliseconds = int(round((safe_seconds - whole_seconds) * 1000))
    if milliseconds == 1000:
        whole_seconds += 1
        milliseconds = 0

    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    remaining_seconds = whole_seconds % 60
    return f"{hours:02}:{minutes:02}:{remaining_seconds:02}{separator}{milliseconds:03}"


def format_ass_timestamp(seconds: float) -> str:
    safe_seconds = max(float(seconds or 0), 0)
    whole_seconds = int(safe_seconds)
    centiseconds = int(round((safe_seconds - whole_seconds) * 100))
    if centiseconds == 100:
        whole_seconds += 1
        centiseconds = 0

    hours = whole_seconds // 3600
    minutes = (whole_seconds % 3600) // 60
    remaining_seconds = whole_seconds % 60
    return f"{hours}:{minutes:02}:{remaining_seconds:02}.{centiseconds:02}"


def resolve_export_speaker_name(
    speaker_id: Optional[str],
    speaker_aliases: Optional[Dict[str, Any]],
) -> Optional[str]:
    if not speaker_id:
        return None

    aliases = normalize_speaker_aliases(speaker_aliases)
    return aliases.get(speaker_id, speaker_id)


def render_txt_export(
    segments: List[Dict[str, Any]],
    *,
    include_timestamps: bool,
    include_speakers: bool,
    speaker_aliases: Optional[Dict[str, Any]],
) -> str:
    lines: List[str] = []

    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        parts: List[str] = []
        if include_timestamps:
            parts.append(f"[{format_export_timestamp(float(segment.get('start_time', 0) or 0), separator=':')[:-4]}]")

        speaker_name = resolve_export_speaker_name(segment.get("speaker"), speaker_aliases)
        if include_speakers and speaker_name:
            parts.append(f"{speaker_name}:")

        if parts:
            lines.append(f"{' '.join(parts)} {text}".strip())
        else:
            lines.append(text)

    return "\n\n".join(lines)


def render_srt_export(segments: List[Dict[str, Any]]) -> str:
    blocks: List[str] = []
    block_index = 1
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        start_time = float(segment.get("start_time", 0) or 0)
        end_time = float(segment.get("end_time", 0) or start_time + 5)
        blocks.append(
            "\n".join(
                [
                    str(block_index),
                    f"{format_export_timestamp(start_time, separator=',')} --> {format_export_timestamp(end_time, separator=',')}",
                    text,
                ]
            )
        )
        block_index += 1

    return "\n\n".join(blocks)


def render_vtt_export(segments: List[Dict[str, Any]]) -> str:
    blocks = ["WEBVTT"]
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        start_time = float(segment.get("start_time", 0) or 0)
        end_time = float(segment.get("end_time", 0) or start_time + 5)
        blocks.append(
            "\n".join(
                [
                    "",
                    f"{format_export_timestamp(start_time, separator='.')} --> {format_export_timestamp(end_time, separator='.')}",
                    text,
                ]
            )
        )

    return "\n".join(blocks).strip() + "\n"


def render_ass_export(
    segments: List[Dict[str, Any]],
    *,
    include_speakers: bool,
    speaker_aliases: Optional[Dict[str, Any]],
) -> str:
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00111111,&H66000000,0,0,0,0,100,100,0,0,1,2,0,2,48,48,40,1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    dialogue_lines: List[str] = []
    for segment in segments:
        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        speaker_name = resolve_export_speaker_name(segment.get("speaker"), speaker_aliases)
        if include_speakers and speaker_name:
            text = f"{speaker_name}: {text}"

        escaped_text = (
            text.replace("\\", r"\\")
            .replace("{", "(")
            .replace("}", ")")
            .replace("\n", r"\N")
        )
        dialogue_lines.append(
            "Dialogue: 0,{start},{end},Default,,0,0,0,,{text}".format(
                start=format_ass_timestamp(float(segment.get("start_time", 0) or 0)),
                end=format_ass_timestamp(float(segment.get("end_time", 0) or 0)),
                text=escaped_text,
            )
        )

    return "\n".join(header + dialogue_lines) + "\n"


def build_transcript_export_payload(
    *,
    content: str,
    segments: Optional[List[Dict[str, Any]]],
    speaker_aliases: Optional[Dict[str, Any]],
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "content": content,
        "segments": build_export_segments(content, segments),
        "speaker_aliases": normalize_speaker_aliases(speaker_aliases),
    }
    if extra:
        payload.update(extra)
    return payload


def build_transcript_export_content(
    content: str,
    segments: Optional[List[Dict[str, Any]]],
    *,
    export_format: Literal["txt", "srt", "vtt", "json", "ass"],
    include_timestamps: bool,
    include_speakers: bool,
    speaker_aliases: Optional[Dict[str, Any]],
    export_payload: Optional[Dict[str, Any]] = None,
) -> str:
    normalized_segments = build_export_segments(content, segments)
    if export_format == "srt":
        return render_srt_export(normalized_segments)
    if export_format == "vtt":
        return render_vtt_export(normalized_segments)
    if export_format == "ass":
        return render_ass_export(
            normalized_segments,
            include_speakers=include_speakers,
            speaker_aliases=speaker_aliases,
        )
    if export_format == "json":
        return json.dumps(
            export_payload
            or build_transcript_export_payload(
                content=content,
                segments=segments,
                speaker_aliases=speaker_aliases,
            ),
            ensure_ascii=False,
            indent=2,
        )
    return render_txt_export(
        normalized_segments,
        include_timestamps=include_timestamps,
        include_speakers=include_speakers,
        speaker_aliases=speaker_aliases,
    )


def build_export_response(
    *,
    base_filename: str,
    export_content: str,
    export_format: Literal["txt", "srt", "vtt", "json", "ass"],
) -> Response:
    filename_root, _filename_ext = os.path.splitext(base_filename)
    safe_filename = f"{filename_root or 'transcript'}.{export_format}"
    media_type = {
        "txt": "text/plain; charset=utf-8",
        "srt": "application/x-subrip; charset=utf-8",
        "vtt": "text/vtt; charset=utf-8",
        "json": "application/json; charset=utf-8",
        "ass": "text/x-ssa; charset=utf-8",
    }[export_format]
    return Response(
        content=export_content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
        },
    )


def build_archive_response(
    *,
    archive_bytes: bytes,
    archive_name: str,
) -> Response:
    return Response(
        content=archive_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive_name}"',
        },
    )


def build_transcript_review_package(
    *,
    base_filename: str,
    transcript: Transcript,
    summaries: List[Summary],
    translated_transcripts: List[TranslatedTranscript],
    comments: List[TranscriptComment],
    revisions: List[TranscriptRevision],
) -> bytes:
    normalized_speaker_aliases = normalize_speaker_aliases(transcript.speaker_aliases)
    transcript_payload = build_transcript_export_payload(
        content=transcript.content,
        segments=transcript.segments,
        speaker_aliases=normalized_speaker_aliases,
        extra={
            "transcript_id": str(transcript.id),
            "video_id": str(transcript.video_id) if transcript.video_id else None,
            "language_code": transcript.language_code,
            "review_status": transcript.review_status,
            "review_assignee": transcript.review_assignee,
        },
    )
    filename_root, _filename_ext = os.path.splitext(base_filename)
    safe_root = filename_root or "transcript"
    summary_rows = [
        {
            "id": str(summary.id),
            "created_at": summary.created_at.isoformat() if summary.created_at else None,
            "status": summary.status,
            "content": summary.content,
            "content_profile": summary.content_profile,
            "summary_metadata": summary.summary_metadata or {},
            "variants": {
                variant.variant_type: variant.content
                for variant in (summary.variants or [])
            },
        }
        for summary in summaries
    ]
    comment_rows = [
        {
            "id": str(comment.id),
            "author_name": comment.author_name,
            "body": comment.body,
            "created_at": comment.created_at.isoformat() if comment.created_at else None,
            "segment_id": comment.segment_id,
            "timestamp_seconds": comment.timestamp_seconds,
        }
        for comment in comments
    ]
    revision_rows = [
        {
            "id": str(revision.id),
            "revision_number": revision.revision_number,
            "reason": revision.reason,
            "created_at": revision.created_at.isoformat() if revision.created_at else None,
            "content": revision.content,
            "segments": revision.segments or [],
            "speaker_aliases": normalize_speaker_aliases(revision.speaker_aliases),
        }
        for revision in revisions
    ]

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{safe_root}/transcript.txt",
            build_transcript_export_content(
                transcript.content,
                transcript.segments,
                export_format="txt",
                include_timestamps=True,
                include_speakers=True,
                speaker_aliases=normalized_speaker_aliases,
                export_payload=transcript_payload,
            ),
        )
        archive.writestr(
            f"{safe_root}/transcript.srt",
            build_transcript_export_content(
                transcript.content,
                transcript.segments,
                export_format="srt",
                include_timestamps=True,
                include_speakers=True,
                speaker_aliases=normalized_speaker_aliases,
                export_payload=transcript_payload,
            ),
        )
        archive.writestr(
            f"{safe_root}/transcript.vtt",
            build_transcript_export_content(
                transcript.content,
                transcript.segments,
                export_format="vtt",
                include_timestamps=True,
                include_speakers=True,
                speaker_aliases=normalized_speaker_aliases,
                export_payload=transcript_payload,
            ),
        )
        archive.writestr(
            f"{safe_root}/transcript.ass",
            build_transcript_export_content(
                transcript.content,
                transcript.segments,
                export_format="ass",
                include_timestamps=True,
                include_speakers=True,
                speaker_aliases=normalized_speaker_aliases,
                export_payload=transcript_payload,
            ),
        )
        archive.writestr(
            f"{safe_root}/transcript.json",
            build_transcript_export_content(
                transcript.content,
                transcript.segments,
                export_format="json",
                include_timestamps=True,
                include_speakers=True,
                speaker_aliases=normalized_speaker_aliases,
                export_payload=transcript_payload,
            ),
        )
        archive.writestr(
            f"{safe_root}/review/comments.json",
            json.dumps(comment_rows, ensure_ascii=False, indent=2),
        )
        archive.writestr(
            f"{safe_root}/review/revisions.json",
            json.dumps(revision_rows, ensure_ascii=False, indent=2),
        )
        archive.writestr(
            f"{safe_root}/summaries.json",
            json.dumps(summary_rows, ensure_ascii=False, indent=2),
        )
        for index, summary in enumerate(summary_rows, start=1):
            archive.writestr(
                f"{safe_root}/summaries/summary-{index}.txt",
                str(summary["content"] or ""),
            )

        for translated_transcript in translated_transcripts:
            translation_payload = build_transcript_export_payload(
                content=translated_transcript.content,
                segments=translated_transcript.segments,
                speaker_aliases=normalized_speaker_aliases,
                extra={
                    "translated_transcript_id": str(translated_transcript.id),
                    "language": translated_transcript.language,
                    "style_guide": translated_transcript.style_guide,
                    "glossary_terms": translated_transcript.glossary_terms or [],
                    "qa_metrics": translated_transcript.qa_metrics or {},
                    "status": translated_transcript.status,
                },
            )
            translation_dir = f"{safe_root}/translations/{translated_transcript.language}"
            archive.writestr(
                f"{translation_dir}/transcript.txt",
                build_transcript_export_content(
                    translated_transcript.content,
                    translated_transcript.segments,
                    export_format="txt",
                    include_timestamps=True,
                    include_speakers=True,
                    speaker_aliases=normalized_speaker_aliases,
                    export_payload=translation_payload,
                ),
            )
            archive.writestr(
                f"{translation_dir}/transcript.ass",
                build_transcript_export_content(
                    translated_transcript.content,
                    translated_transcript.segments,
                    export_format="ass",
                    include_timestamps=True,
                    include_speakers=True,
                    speaker_aliases=normalized_speaker_aliases,
                    export_payload=translation_payload,
                ),
            )
            archive.writestr(
                f"{translation_dir}/transcript.json",
                build_transcript_export_content(
                    translated_transcript.content,
                    translated_transcript.segments,
                    export_format="json",
                    include_timestamps=True,
                    include_speakers=True,
                    speaker_aliases=normalized_speaker_aliases,
                    export_payload=translation_payload,
                ),
            )

    return buffer.getvalue()


def resolve_video_storage_path(
    filename: str,
    *,
    storage_path: Optional[str] = None,
) -> str:
    return storage_backend.resolve_video_path(
        filename,
        storage_uri=storage_path,
    )


def get_video_storage_path(video: Video, db: Session) -> str:
    try:
        resolved_path = resolve_video_storage_path(
            video.filename,
            storage_path=video.storage_path,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if video.storage_path is None:
        video.storage_path = canonicalize_storage_path(resolved_path)
        db.commit()
        db.refresh(video)

    return resolved_path


def canonicalize_storage_path(storage_path: Optional[str]) -> Optional[str]:
    """Normalize optional storage paths before comparing or persisting them."""
    return storage_backend.normalize_uri(storage_path)


def merge_video_metadata(
    existing_metadata: Optional[Dict[str, Any]],
    incoming_metadata: Optional[Dict[str, Any]],
    file_hash: Optional[str],
) -> Dict[str, Any]:
    """Preserve known metadata while allowing new watcher-provided values to win."""
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
    """Match videos by canonical path first, then by file hash, then by filename fallback."""
    if storage_path:
        existing_video = db.query(Video).filter(Video.storage_path == storage_path).first()
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


def build_upload_storage_target(filename: str, db: Session):
    """Allocate a non-destructive managed-media target for uploaded files."""
    return storage_backend.prepare_upload_target(
        filename,
        is_reserved=lambda candidate_uri: find_existing_video(
            db,
            filename=filename,
            storage_path=candidate_uri,
        )[0]
        is not None,
    )


def paginate_query(query: SqlAlchemyQuery, *, limit: int, offset: int) -> tuple[List[Any], int]:
    """Paginate an ORM query while preserving the caller's ordering for result rows."""
    total = query.order_by(None).count()
    items = query.limit(limit).offset(offset).all()
    return items, total


def paginate_items(items: List[Any], *, limit: int, offset: int) -> tuple[List[Any], int]:
    """Paginate an in-memory collection when SQL-level pagination is not practical."""
    total = len(items)
    return items[offset : offset + limit], total


def build_paginated_response(
    items: List[Any],
    *,
    total: int,
    limit: int,
    offset: int,
    **extra: Any,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }
    response.update(extra)
    return response


def build_video_library_stats(db: Session) -> VideoLibraryStatsResponse:
    status_column = func.lower(Video.status)
    return VideoLibraryStatsResponse(
        total_videos=db.query(Video).count(),
        processing_videos=db.query(Video).filter(status_column.in_(["pending", "processing"])).count(),
        ready_videos=db.query(Video).filter(status_column.in_(["completed", "transcribed"])).count(),
        failed_videos=db.query(Video).filter(status_column.in_(["error", "failed"])).count(),
    )


def build_summary_response(summary: Summary) -> SummaryResponse:
    variants = {
        variant.variant_type: variant.content
        for variant in (summary.variants or [])
    }
    return SummaryResponse(
        id=str(summary.id),
        transcript_id=str(summary.transcript_id),
        content=summary.content,
        content_profile=summary.content_profile or "generic",
        summary_metadata=summary.summary_metadata or {},
        status=summary.status,
        created_at=summary.created_at,
        variants=variants,
    )


@app.get("/events/stream")
async def stream_live_updates(
    request: Request,
    video_id: Optional[str] = None,
    transcript_id: Optional[str] = None,
):
    filters = build_live_update_filters(video_id=video_id, transcript_id=transcript_id)
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }

    return StreamingResponse(
        live_update_manager.stream(request, filters),
        headers=headers,
        media_type="text/event-stream",
    )


@app.websocket("/events/ws")
async def websocket_live_updates(
    websocket: WebSocket,
    video_id: Optional[str] = None,
    transcript_id: Optional[str] = None,
) -> None:
    filters = build_live_update_filters(video_id=video_id, transcript_id=transcript_id)
    await live_update_manager.stream_websocket(websocket, filters)


# Pydantic models for request/response
class VideoCreate(BaseModel):
    filename: str
    file_hash: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None
    storage_path: Optional[str] = None


class VideoCheck(BaseModel):
    filename: str
    file_hash: Optional[str] = None
    storage_path: Optional[str] = None


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: str
    created_at: Any
    file_hash: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None
    storage_path: Optional[str] = None


class YoutubeDownloadRequest(BaseModel):
    url: str


class TranscriptionJobCreate(BaseModel):
    video_id: str


class TranscriptionJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    status: str
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None


class LeaseWorkerRequest(BaseModel):
    worker_id: str


class TranscriptionJobUpdate(LeaseWorkerRequest):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class SummarizationJobCreate(BaseModel):
    transcript_id: str
    content_profile: Optional[
        Literal["generic", "interview", "lecture", "meeting", "podcast"]
    ] = None


class SummarizationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    content_profile: Optional[str] = None
    status: str
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None


class SummarizationJobUpdate(LeaseWorkerRequest):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class SummaryCreate(BaseModel):
    transcript_id: str
    content: str
    content_profile: str = "generic"
    summary_metadata: Optional[Dict[str, Any]] = None
    status: str = "completed"
    variants: Optional[Dict[str, Any]] = None


class SummaryResponse(BaseModel):
    id: str
    transcript_id: str
    content: str
    content_profile: str
    summary_metadata: Dict[str, Any]
    status: str
    created_at: Any
    variants: Dict[str, str]


class TranslationGlossaryTermInput(BaseModel):
    source_term: str
    target_term: str
    notes: Optional[str] = None


class TranslationJobCreate(BaseModel):
    transcript_id: str
    target_language: str
    source_language: Optional[str] = None
    style_guide: Optional[str] = None
    glossary_terms: Optional[List[TranslationGlossaryTermInput]] = None


class TranslationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    source_language: Optional[str]
    target_language: str
    style_guide: Optional[str] = None
    glossary_terms: Optional[List[Dict[str, str]]] = None
    status: str
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None


class TranslationJobUpdate(LeaseWorkerRequest):
    status: Optional[str] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class TranslatedTranscriptCreate(BaseModel):
    transcript_id: str
    language: str
    content: str
    segments: Optional[List[Dict[str, Any]]] = None
    style_guide: Optional[str] = None
    glossary_terms: Optional[List[Dict[str, str]]] = None
    qa_metrics: Optional[Dict[str, Any]] = None
    status: str = "completed"


class TranslatedTranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    language: str
    content: str
    segments: Optional[List[Dict[str, Any]]] = None
    style_guide: Optional[str] = None
    glossary_terms: Optional[List[Dict[str, str]]] = None
    qa_metrics: Optional[Dict[str, Any]] = None
    status: str
    created_at: Any


class TranscriptSegmentsUpdate(BaseModel):
    segments: List[Dict[str, Any]]
    content: Optional[str] = None


class TranscriptSpeakerAliasUpdate(BaseModel):
    speaker_aliases: Dict[str, str]


class TranscriptReviewUpdate(BaseModel):
    review_status: Literal["draft", "in_review", "approved", "needs_changes"]
    review_assignee: Optional[str] = None


class TranscriptCommentCreate(BaseModel):
    author_name: Optional[str] = None
    body: str
    segment_id: Optional[int] = None
    timestamp_seconds: Optional[float] = None


class TranscriptCreate(BaseModel):
    video_id: str
    source_type: str = "video"
    content: str
    format: str = "txt"
    status: str = "completed"
    language_code: Optional[str] = None
    speaker_aliases: Optional[Dict[str, str]] = None
    review_status: str = "draft"
    review_assignee: Optional[str] = None
    segments: Optional[List[Dict[str, Any]]] = None


class TranscriptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    video_id: str
    source_type: str
    content: str
    format: str
    status: str
    language_code: Optional[str] = None
    speaker_aliases: Optional[Dict[str, str]] = None
    review_status: str
    review_assignee: Optional[str] = None
    created_at: Any
    segments: Optional[List[Dict[str, Any]]] = None


class TranscriptRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    revision_number: int
    reason: str
    content: str
    speaker_aliases: Optional[Dict[str, str]] = None
    created_at: Any
    segments: Optional[List[Dict[str, Any]]] = None


class TranscriptCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transcript_id: str
    segment_id: Optional[int] = None
    timestamp_seconds: Optional[float] = None
    author_name: Optional[str] = None
    body: str
    created_at: Any


class SearchResultResponse(BaseModel):
    video_id: str
    video_title: str
    transcript_id: str
    segment_id: int
    start_time: float
    end_time: float
    text: str
    speaker: str
    language_code: Optional[str] = None
    review_status: Optional[str] = None


class UnifiedJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    legacy_job_table: str
    legacy_job_id: str
    job_type: str
    subject_type: str
    subject_id: str
    status: str
    priority: int
    payload: Optional[Dict[str, Any]] = None
    progress: Optional[float] = None
    attempt_count: int
    worker_id: Optional[str] = None
    lease_expires_at: Optional[Any] = None
    created_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None


class JobAttemptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    attempt_number: int
    worker_id: Optional[str] = None
    status: str
    started_at: Any
    completed_at: Optional[Any] = None
    processing_time_seconds: Optional[float] = None
    error_details: Optional[Dict[str, Any]] = None
    created_at: Any


class PaginatedResponse(BaseModel, Generic[ItemT]):
    items: List[ItemT]
    total: int
    limit: int
    offset: int


class VideoLibraryStatsResponse(BaseModel):
    total_videos: int
    processing_videos: int
    ready_videos: int
    failed_videos: int


class VideoListResponse(PaginatedResponse[VideoResponse]):
    stats: VideoLibraryStatsResponse


class VideoUpdate(BaseModel):
    status: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None


@app.get("/")
def read_root():
    """Root endpoint."""
    return {"message": "Video Transcriber API"}


@app.get("/healthz")
def read_health():
    database_status = "ok"
    status_code = 200

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as error:
        logger.error("Health check database probe failed: %s", error)
        database_status = "error"
        status_code = 503

    payload = {
        "status": "ok" if database_status == "ok" else "degraded",
        "database": database_status,
        "storage_backend": storage_backend.backend_name,
        "live_updates_notify_enabled": LIVE_UPDATES_NOTIFY_ENABLED,
    }
    return Response(
        content=json.dumps(payload),
        media_type="application/json",
        status_code=status_code,
    )


@app.get("/metrics")
def read_metrics(
    lookback_hours: int = Query(default=168, ge=1, le=24 * 30),
):
    return summarize_metric_events(lookback_hours=lookback_hours)


@app.post("/videos/")
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload a video file for transcription.

    Args:
        background_tasks: FastAPI background tasks
        file: The video file to upload
        db: Database session

    Returns:
        The created video object
    """
    logger.info(f"Received video upload: {file.filename}")

    # Save the video file
    upload_target = build_upload_storage_target(file.filename, db)
    try:
        os.makedirs(os.path.dirname(upload_target.local_path), exist_ok=True)
        with open(upload_target.local_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Error saving video file: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error saving video file: {str(e)}")

    # Create video record
    video = Video(filename=file.filename, storage_path=upload_target.storage_uri)
    db.add(video)
    db.flush()
    sync_video_storage_objects(db, video)
    db.commit()
    db.refresh(video)

    create_transcription_job_for_video(str(video.id))

    await publish_live_update(
        EVENT_VIDEO_CREATED,
        filename=video.filename,
        status=video.status,
        video_id=str(video.id),
    )

    return build_video_response(video)


@app.post("/videos/youtube", response_model=VideoResponse)
async def download_youtube_video(
    background_tasks: BackgroundTasks,
    request: YoutubeDownloadRequest,
    db: Session = Depends(get_db),
):
    """
    Download a video from YouTube (or other supported sites) and start transcription.
    """
    import yt_dlp
    import uuid

    logger.info(f"Received YouTube download request: {request.url}")

    # Generate a unique filename using UUID to avoid collisions
    unique_id = str(uuid.uuid4())[:8]
    
    try:
        with tempfile.TemporaryDirectory(prefix="video-transcriber-ytdlp-") as temp_dir:
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': os.path.join(temp_dir, f'%(title)s_{unique_id}.%(ext)s'),
                'restrictfilenames': True,
                'noplaylist': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(request.url, download=True)
                filename = ydl.prepare_filename(info)
                basename = os.path.basename(filename)

            logger.info("Successfully downloaded YouTube video to: %s", filename)

            upload_target = build_upload_storage_target(basename, db)
            os.makedirs(os.path.dirname(upload_target.local_path), exist_ok=True)
            shutil.move(filename, upload_target.local_path)

            video = Video(filename=basename, storage_path=upload_target.storage_uri)
            db.add(video)
            db.flush()
            sync_video_storage_objects(db, video)
            db.commit()
            db.refresh(video)

            create_transcription_job_for_video(str(video.id))

            await publish_live_update(
                EVENT_VIDEO_CREATED,
                filename=video.filename,
                status=video.status,
                video_id=str(video.id),
            )

            return build_video_response(video)
    except Exception as e:
        logger.error(f"Error downloading YouTube video: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading YouTube video: {str(e)}")


@app.post("/videos/register", response_model=VideoResponse)
async def register_video(video_data: VideoCreate, db: Session = Depends(get_db)):
    """
    Register a video file that already exists in the videos directory.
    Used by the watcher service.

    Args:
        video_data: The video data
        db: Database session

    Returns:
        The created or updated video object
    """
    logger.info(f"Registering video: {video_data.filename}")

    # Check if the video file exists
    filename = video_data.filename
    requested_storage_path = canonicalize_storage_path(video_data.storage_path)
    try:
        resolved_file_path = resolve_video_storage_path(
            filename,
            storage_path=requested_storage_path,
        )
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    canonical_storage_path = requested_storage_path or canonicalize_storage_path(
        resolved_file_path
    )

    existing_video, match_reason = find_existing_video(
        db,
        filename=video_data.filename,
        storage_path=canonical_storage_path,
        file_hash=video_data.file_hash,
    )
    if existing_video:
        logger.info("Video %s already exists via %s; syncing canonical metadata", video_data.filename, match_reason)
        existing_video.filename = video_data.filename
        existing_video.file_hash = video_data.file_hash or existing_video.file_hash
        existing_video.storage_path = canonical_storage_path
        existing_video.video_metadata = merge_video_metadata(
            existing_video.video_metadata,
            video_data.video_metadata,
            video_data.file_hash,
        )
        sync_video_storage_objects(db, existing_video)
        db.commit()
        db.refresh(existing_video)
        await publish_live_update(
            EVENT_VIDEO_UPDATED,
            filename=existing_video.filename,
            status=existing_video.status,
            video_id=str(existing_video.id),
        )
        return build_video_response(existing_video)

    # Create a new video record
    video = Video(
        filename=video_data.filename,
        file_hash=video_data.file_hash,
        storage_path=canonical_storage_path,
        status="pending",
        video_metadata=merge_video_metadata(None, video_data.video_metadata, video_data.file_hash),
    )

    db.add(video)
    db.flush()
    sync_video_storage_objects(db, video)
    db.commit()
    db.refresh(video)

    logger.info(f"Added video {video_data.filename} to the database with ID: {video.id}")
    await publish_live_update(
        EVENT_VIDEO_CREATED,
        filename=video.filename,
        status=video.status,
        video_id=str(video.id),
    )

    return build_video_response(video)


@app.post("/videos/check", response_model=Optional[VideoResponse])
async def check_video_exists(video_check: VideoCheck, db: Session = Depends(get_db)):
    """
    Check if a video exists in the database by filename or file hash.
    Used by the watcher service.

    Args:
        video_check: The video check data
        db: Database session

    Returns:
        The video object if found, None otherwise
    """
    logger.info(f"Checking if video exists: {video_check.filename}")

    existing_video, match_reason = find_existing_video(
        db,
        filename=video_check.filename,
        storage_path=canonicalize_storage_path(video_check.storage_path),
        file_hash=video_check.file_hash,
    )
    if existing_video:
        logger.info("Video %s found in the database via %s", video_check.filename, match_reason)
        return build_video_response(existing_video)

    logger.info(f"Video {video_check.filename} not found in the database")
    return None


@app.post("/transcription-jobs/", response_model=TranscriptionJobResponse)
async def create_transcription_job_endpoint(job_data: TranscriptionJobCreate, db: Session = Depends(get_db)):
    """
    Create a new transcription job.
    Used by the watcher service.

    Args:
        job_data: The job data
        db: Database session

    Returns:
        The created transcription job
    """
    logger.info(f"Creating transcription job for video: {job_data.video_id}")

    # Check if the video exists
    video = db.query(Video).filter(Video.id == job_data.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {job_data.video_id}")

    try:
        unified_job = create_transcription_job_for_video(job_data.video_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    return get_legacy_job_or_404(
        db,
        job_type="transcription",
        legacy_job_id=str(unified_job["legacy_job_id"]),
    )


@app.post("/transcription-jobs/claim", response_model=Optional[TranscriptionJobResponse])
async def claim_transcription_job(request_data: LeaseWorkerRequest, db: Session = Depends(get_db)):
    """Atomically claim the next available transcription job."""
    unified_job = claim_next_transcription_job(request_data.worker_id)
    if not unified_job:
        return None

    return get_legacy_job_or_404(
        db,
        job_type="transcription",
        legacy_job_id=str(unified_job["legacy_job_id"]),
    )


@app.post("/transcription-jobs/{job_id}/heartbeat", response_model=TranscriptionJobResponse)
async def heartbeat_transcription_job(job_id: str, request_data: LeaseWorkerRequest, db: Session = Depends(get_db)):
    """Refresh a transcription job lease for the owning worker."""
    try:
        heartbeat_legacy_job("transcription", job_id, request_data.worker_id)
        job = get_legacy_job_or_404(db, job_type="transcription", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.get("/transcription-jobs", response_model=PaginatedResponse[TranscriptionJobResponse])
async def get_transcription_jobs(
    status: Optional[str] = None,
    video_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get all transcription jobs, optionally filtered by status and video_id.
    Used by the transcription worker and frontend.

    Args:
        status: Optional status to filter by
        video_id: Optional video ID to filter by
        db: Database session

    Returns:
        List of transcription jobs
    """
    query = db.query(TranscriptionJob)

    if status:
        query = query.filter(TranscriptionJob.status == status)
    
    if video_id:
        query = query.filter(TranscriptionJob.video_id == video_id)

    query = query.order_by(TranscriptionJob.created_at.desc())
    jobs, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@app.get("/transcription-jobs/{job_id}", response_model=TranscriptionJobResponse)
async def get_transcription_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get a transcription job by ID.

    Args:
        job_id: The ID of the job
        db: Database session

    Returns:
        The transcription job
    """
    job = db.query(TranscriptionJob).filter(TranscriptionJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Transcription job not found: {job_id}")
    return job


@app.post("/transcription-jobs/{job_id}/complete", response_model=TranscriptionJobResponse)
async def complete_transcription_job(job_id: str, update_data: TranscriptionJobUpdate, db: Session = Depends(get_db)):
    """
    Mark a transcription job as completed.
    Used by the transcription worker.

    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session

    Returns:
        The updated transcription job
    """
    try:
        complete_legacy_job(
            "transcription",
            job_id,
            update_data.worker_id,
            processing_time=update_data.processing_time_seconds,
            error_details=update_data.error_details,
        )
        job = get_legacy_job_or_404(db, job_type="transcription", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.post("/transcription-jobs/{job_id}/fail", response_model=TranscriptionJobResponse)
async def fail_transcription_job(job_id: str, update_data: TranscriptionJobUpdate, db: Session = Depends(get_db)):
    """
    Mark a transcription job as failed.
    Used by the transcription worker.

    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session

    Returns:
        The updated transcription job
    """
    try:
        fail_legacy_job(
            "transcription",
            job_id,
            update_data.worker_id,
            error_details=update_data.error_details,
        )
        job = get_legacy_job_or_404(db, job_type="transcription", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.post("/transcription-jobs/{job_id}/retry", response_model=TranscriptionJobResponse)
async def retry_transcription_job(job_id: str, db: Session = Depends(get_db)):
    """
    Retry a failed transcription job by setting its status back to pending.

    Args:
        job_id: The ID of the job to retry
        db: Database session

    Returns:
        The updated transcription job
    """
    try:
        retry_legacy_job("transcription", job_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    logger.info("Transcription job %s has been reset to pending status for retry", job_id)
    return get_legacy_job_or_404(db, job_type="transcription", legacy_job_id=job_id)


@app.post("/summarization-jobs/", response_model=SummarizationJobResponse)
async def create_summarization_job_endpoint(job_data: SummarizationJobCreate, db: Session = Depends(get_db)):
    """
    Create a new summarization job.
    Used by the transcription worker.

    Args:
        job_data: The job data
        db: Database session

    Returns:
        The created summarization job
    """
    logger.info(f"Creating summarization job for transcript: {job_data.transcript_id}")

    # Check if the transcript exists
    transcript = db.query(Transcript).filter(Transcript.id == job_data.transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {job_data.transcript_id}")

    try:
        unified_job = create_summarization_job_for_transcript(
            job_data.transcript_id,
            content_profile=job_data.content_profile,
        )
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    return get_legacy_job_or_404(
        db,
        job_type="summarization",
        legacy_job_id=str(unified_job["legacy_job_id"]),
    )


@app.post("/summarization-jobs/claim", response_model=Optional[SummarizationJobResponse])
async def claim_summarization_job(request_data: LeaseWorkerRequest, db: Session = Depends(get_db)):
    """Atomically claim the next available summarization job."""
    unified_job = claim_next_summarization_job(request_data.worker_id)
    if not unified_job:
        return None

    return get_legacy_job_or_404(
        db,
        job_type="summarization",
        legacy_job_id=str(unified_job["legacy_job_id"]),
    )


@app.post("/summarization-jobs/{job_id}/heartbeat", response_model=SummarizationJobResponse)
async def heartbeat_summarization_job(job_id: str, request_data: LeaseWorkerRequest, db: Session = Depends(get_db)):
    """Refresh a summarization job lease for the owning worker."""
    try:
        heartbeat_legacy_job("summarization", job_id, request_data.worker_id)
        job = get_legacy_job_or_404(db, job_type="summarization", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.get("/summarization-jobs", response_model=PaginatedResponse[SummarizationJobResponse])
async def get_summarization_jobs(
    status: Optional[str] = None,
    transcript_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get all summarization jobs, optionally filtered by status and transcript_id.
    Used by the summarization worker and frontend.

    Args:
        status: Optional status to filter by
        transcript_id: Optional transcript ID to filter by
        db: Database session

    Returns:
        List of summarization jobs
    """
    query = db.query(SummarizationJob)

    if status:
        query = query.filter(SummarizationJob.status == status)
    
    if transcript_id:
        query = query.filter(SummarizationJob.transcript_id == transcript_id)

    query = query.order_by(SummarizationJob.created_at.desc())
    jobs, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@app.get("/summarization-jobs/{job_id}", response_model=SummarizationJobResponse)
async def get_summarization_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get a summarization job by ID.

    Args:
        job_id: The ID of the job
        db: Database session

    Returns:
        The summarization job
    """
    job = db.query(SummarizationJob).filter(SummarizationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Summarization job not found: {job_id}")
    return job


@app.post("/summarization-jobs/{job_id}/complete", response_model=SummarizationJobResponse)
async def complete_summarization_job(job_id: str, update_data: SummarizationJobUpdate, db: Session = Depends(get_db)):
    """
    Mark a summarization job as completed.
    Used by the summarization worker.

    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session

    Returns:
        The updated summarization job
    """
    try:
        complete_legacy_job(
            "summarization",
            job_id,
            update_data.worker_id,
            processing_time=update_data.processing_time_seconds,
            error_details=update_data.error_details,
        )
        job = get_legacy_job_or_404(db, job_type="summarization", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.post("/summarization-jobs/{job_id}/fail", response_model=SummarizationJobResponse)
async def fail_summarization_job(job_id: str, update_data: SummarizationJobUpdate, db: Session = Depends(get_db)):
    """
    Mark a summarization job as failed.
    Used by the summarization worker.

    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session

    Returns:
        The updated summarization job
    """
    try:
        fail_legacy_job(
            "summarization",
            job_id,
            update_data.worker_id,
            error_details=update_data.error_details,
        )
        job = get_legacy_job_or_404(db, job_type="summarization", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.post("/summaries/", response_model=SummaryResponse)
async def create_summary(summary_data: SummaryCreate, db: Session = Depends(get_db)):
    """
    Create a new summary.
    Used by the summarization worker.

    Args:
        summary_data: The summary data
        db: Database session

    Returns:
        The created summary
    """
    logger.info(f"Creating summary for transcript: {summary_data.transcript_id}")

    # Check if the transcript exists
    transcript = db.query(Transcript).filter(Transcript.id == summary_data.transcript_id).first()
    if not transcript:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found: {summary_data.transcript_id}",
        )

    # Create a summary
    summary = Summary(
        transcript_id=summary_data.transcript_id,
        content=summary_data.content,
        content_profile=summary_data.content_profile,
        summary_metadata=summary_data.summary_metadata or {},
        status=summary_data.status,
    )
    db.add(summary)
    db.flush()
    sync_summary_variants(db, summary, variants=summary_data.variants)
    db.commit()
    db.refresh(summary)

    await publish_live_update(
        EVENT_SUMMARY_CREATED,
        summary_id=str(summary.id),
        transcript_id=str(summary.transcript_id),
    )

    return build_summary_response(summary)


@app.patch("/transcripts/{transcript_id}", response_model=TranscriptResponse)
async def update_transcript(transcript_id: str, update_data: dict, db: Session = Depends(get_db)):
    """
    Update a transcript.
    Used by the summarization worker.

    Args:
        transcript_id: The ID of the transcript
        update_data: The update data
        db: Database session

    Returns:
        The updated transcript
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {transcript_id}")

    if "status" in update_data:
        transcript.status = update_data["status"]

    db.commit()
    db.refresh(transcript)

    await publish_live_update(
        EVENT_TRANSCRIPT_UPDATED,
        status=transcript.status,
        transcript_id=str(transcript.id),
        video_id=str(transcript.video_id) if transcript.video_id else None,
    )

    return transcript


@app.put("/transcripts/{transcript_id}/segments", response_model=TranscriptResponse)
async def update_transcript_segments(transcript_id: str, update_data: TranscriptSegmentsUpdate, db: Session = Depends(get_db)):
    """
    Update the segments (and optionally the full text content) of a transcript.
    Used by the frontend for interactive transcript editing.
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {transcript_id}")

    transcript.segments = update_data.segments
    if update_data.content is not None:
        transcript.content = update_data.content

    sync_transcript_segment_rows(db, transcript)
    sync_transcript_speaker_rows(db, transcript)
    create_transcript_revision(db, transcript, reason="segment_edit")
    sync_transcript_search_rows(db, transcript)
    db.commit()
    db.refresh(transcript)

    await publish_live_update(
        EVENT_TRANSCRIPT_UPDATED,
        transcript_id=str(transcript.id),
        video_id=str(transcript.video_id) if transcript.video_id else None,
    )

    return transcript


@app.put("/transcripts/{transcript_id}/speaker-aliases", response_model=TranscriptResponse)
async def update_transcript_speaker_aliases(
    transcript_id: str,
    update_data: TranscriptSpeakerAliasUpdate,
    db: Session = Depends(get_db),
):
    """
    Persist transcript speaker aliases server-side.
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {transcript_id}")

    transcript.speaker_aliases = normalize_speaker_aliases(update_data.speaker_aliases)
    sync_transcript_speaker_rows(db, transcript)
    create_transcript_revision(db, transcript, reason="speaker_alias_update")
    db.commit()
    db.refresh(transcript)

    await publish_live_update(
        EVENT_TRANSCRIPT_UPDATED,
        transcript_id=str(transcript.id),
        video_id=str(transcript.video_id) if transcript.video_id else None,
    )

    return transcript


@app.patch("/transcripts/{transcript_id}/review", response_model=TranscriptResponse)
async def update_transcript_review(
    transcript_id: str,
    update_data: TranscriptReviewUpdate,
    db: Session = Depends(get_db),
):
    """
    Persist shared transcript review metadata.
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {transcript_id}")

    transcript.review_status = update_data.review_status
    transcript.review_assignee = update_data.review_assignee.strip() if update_data.review_assignee else None
    create_transcript_revision(db, transcript, reason=f"review_status_{update_data.review_status}")
    db.commit()
    db.refresh(transcript)

    await publish_live_update(
        EVENT_TRANSCRIPT_UPDATED,
        transcript_id=str(transcript.id),
        video_id=str(transcript.video_id) if transcript.video_id else None,
        status=transcript.review_status,
    )

    return transcript


@app.get("/transcripts/{transcript_id}/comments", response_model=List[TranscriptCommentResponse])
def list_transcript_comments(transcript_id: str, db: Session = Depends(get_db)):
    """
    List transcript comments newest-first.
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return (
        db.query(TranscriptComment)
        .filter(TranscriptComment.transcript_id == transcript_id)
        .order_by(TranscriptComment.created_at.desc())
        .all()
    )


@app.post("/transcripts/{transcript_id}/comments", response_model=TranscriptCommentResponse)
async def create_transcript_comment(
    transcript_id: str,
    comment_data: TranscriptCommentCreate,
    db: Session = Depends(get_db),
):
    """
    Create a timestamp-linked transcript comment.
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    body = comment_data.body.strip()
    if not body:
        raise HTTPException(status_code=400, detail="Comment body must not be empty")

    comment = TranscriptComment(
        transcript_id=transcript_id,
        segment_id=comment_data.segment_id,
        timestamp_seconds=comment_data.timestamp_seconds,
        author_name=comment_data.author_name.strip() if comment_data.author_name else None,
        body=body,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment


@app.delete("/transcript-comments/{comment_id}", status_code=204)
def delete_transcript_comment(comment_id: str, db: Session = Depends(get_db)):
    """
    Delete a transcript comment.
    """
    comment = db.query(TranscriptComment).filter(TranscriptComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Transcript comment not found")

    db.delete(comment)
    db.commit()
    return Response(status_code=204)


@app.post("/transcripts/", response_model=TranscriptResponse)
async def create_transcript(transcript_data: TranscriptCreate, db: Session = Depends(get_db)):
    """
    Create a new transcript.
    Used by the transcription worker.

    Args:
        transcript_data: The transcript data
        db: Database session

    Returns:
        The created transcript
    """
    logger.info(f"Creating transcript for video: {transcript_data.video_id}")

    # Check if the video exists
    video = db.query(Video).filter(Video.id == transcript_data.video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {transcript_data.video_id}")

    # Create a transcript
    transcript = Transcript(
        video_id=transcript_data.video_id,
        source_type=transcript_data.source_type,
        content=transcript_data.content,
        format=transcript_data.format,
        status=transcript_data.status,
        language_code=transcript_data.language_code,
        speaker_aliases=normalize_speaker_aliases(transcript_data.speaker_aliases),
        review_status=transcript_data.review_status,
        review_assignee=transcript_data.review_assignee,
        segments=transcript_data.segments,
    )
    db.add(transcript)
    db.flush()
    sync_transcript_segment_rows(db, transcript)
    sync_transcript_speaker_rows(db, transcript)
    create_transcript_revision(db, transcript, reason="initial_import")
    sync_transcript_search_rows(db, transcript)
    db.commit()
    db.refresh(transcript)

    await publish_live_update(
        EVENT_TRANSCRIPTION_CREATED,
        transcript_id=str(transcript.id),
        video_id=str(transcript.video_id),
    )

    return transcript


@app.patch("/videos/{video_id}", response_model=VideoResponse)
async def update_video(video_id: str, update_data: VideoUpdate, db: Session = Depends(get_db)):
    """
    Update a video.
    Used by the transcription worker.

    Args:
        video_id: The ID of the video
        update_data: The update data
        db: Database session

    Returns:
        The updated video
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail=f"Video not found: {video_id}")

    if update_data.status is not None:
        video.status = update_data.status

    if update_data.video_metadata is not None:
        video.video_metadata = update_data.video_metadata

    db.commit()
    db.refresh(video)

    await publish_live_update(
        EVENT_VIDEO_UPDATED,
        filename=video.filename,
        status=video.status,
        video_id=str(video.id),
    )

    return build_video_response(video)


@app.get("/videos/", response_model=VideoListResponse)
def list_videos(
    status_group: Literal["all", "processing", "ready", "failed"] = Query(default="all"),
    date_window_days: Optional[int] = Query(default=None, ge=1, le=3650),
    q: Optional[str] = Query(default=None),
    sort: Literal["newest", "oldest", "name"] = Query(default="newest"),
    limit: int = Query(default=18, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List all videos.

    Args:
        db: Database session

    Returns:
        List of videos
    """
    query = db.query(Video)
    status_column = func.lower(Video.status)

    if status_group == "processing":
        query = query.filter(status_column.in_(["pending", "processing"]))
    elif status_group == "ready":
        query = query.filter(status_column.in_(["completed", "transcribed"]))
    elif status_group == "failed":
        query = query.filter(status_column.in_(["error", "failed"]))

    if date_window_days is not None:
        query = query.filter(Video.created_at >= datetime.utcnow() - timedelta(days=date_window_days))

    normalized_query = (q or "").strip().lower()
    if normalized_query:
        query = query.filter(
            func.lower(func.coalesce(Video.filename, "")).like(f"%{normalized_query}%")
        )

    if sort == "name":
        query = query.order_by(Video.filename.asc(), Video.created_at.desc())
    elif sort == "oldest":
        query = query.order_by(Video.created_at.asc(), Video.filename.asc())
    else:
        query = query.order_by(Video.created_at.desc(), Video.filename.asc())

    videos, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(
        videos,
        total=total,
        limit=limit,
        offset=offset,
        stats=build_video_library_stats(db),
    )


@app.get("/videos/{video_id}")
def get_video(video_id: str, db: Session = Depends(get_db)):
    """
    Get a video by ID.

    Args:
        video_id: The ID of the video
        db: Database session

    Returns:
        The video object
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return video


@app.get("/videos/{video_id}/download")
def download_video(video_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Download a video by ID with support for HTTP Range requests.

    Args:
        video_id: The ID of the video
        request: The FastAPI request object
        db: Database session

    Returns:
        The video file with support for partial content
    """
    video = db.query(Video).filter(Video.id == video_id).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    file_path = get_video_storage_path(video, db)

    file_stat = os.stat(file_path)
    file_size = file_stat[stat.ST_SIZE]

    # Determine the media type based on file extension
    import mimetypes
    import urllib.parse
    from email.utils import formatdate

    file_extension = os.path.splitext(video.filename)[1].lower()
    media_type = mimetypes.guess_type(video.filename)[0]

    # Default to video/mp4 if we can't determine the media type
    if not media_type:
        if file_extension in [".mp4", ".m4v"]:
            media_type = "video/mp4"
        elif file_extension in [".mov", ".qt"]:
            media_type = "video/quicktime"
        elif file_extension in [".avi"]:
            media_type = "video/x-msvideo"
        elif file_extension in [".wmv"]:
            media_type = "video/x-ms-wmv"
        elif file_extension in [".webm"]:
            media_type = "video/webm"
        else:
            media_type = "video/mp4"  # Default fallback

    # Use RFC 6266/5987 encoding for the filename to handle non-Latin-1 characters
    ascii_filename = video.filename.encode("ascii", "replace").decode("ascii")
    utf8_filename = urllib.parse.quote(video.filename.encode("utf-8"))
    etag = f"W/\"{file_size}-{int(file_stat.st_mtime)}\""
    cache_headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=604800, immutable",
        "Content-Disposition": f"inline; filename=\"{ascii_filename}\"; filename*=UTF-8''{utf8_filename}",
        "ETag": etag,
        "Last-Modified": formatdate(file_stat.st_mtime, usegmt=True),
    }

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)

    # Check if Range header exists
    range_header = request.headers.get("Range", None)

    # If no Range header, return the full file
    if range_header is None:
        return FileResponse(file_path, headers=cache_headers, media_type=media_type)

    # Parse the Range header
    range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not range_match:
        # If Range header is invalid, return the full file
        return FileResponse(file_path, headers=cache_headers, media_type=media_type)

    # Extract start and end bytes
    start_byte = int(range_match.group(1))
    end_byte_str = range_match.group(2)
    end_byte = int(end_byte_str) if end_byte_str else file_size - 1

    # Ensure end byte is not beyond file size
    end_byte = min(end_byte, file_size - 1)

    # Calculate content length
    content_length = end_byte - start_byte + 1

    # Define a generator to stream the file in chunks
    def file_iterator(start, end, chunk_size=8192):
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(chunk_size, remaining))
                if not chunk:
                    break
                yield chunk
                remaining -= len(chunk)

    headers = {
        **cache_headers,
        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
        "Content-Length": str(content_length),
    }

    logger.info(f"Serving video {video.filename} with media type: {media_type}")

    # Return a streaming response with the appropriate status code and headers
    return StreamingResponse(
        file_iterator(start_byte, end_byte),
        status_code=206,  # Partial Content
        headers=headers,
        media_type=media_type,
    )


@app.get("/transcripts/", response_model=PaginatedResponse[TranscriptResponse])
def list_transcripts(
    video_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List all transcripts, optionally filtered by video ID.

    Args:
        video_id: Optional video ID to filter by
        db: Database session

    Returns:
        List of transcripts
    """
    query = db.query(Transcript)
    if video_id:
        query = query.filter(Transcript.video_id == video_id)
    query = query.order_by(Transcript.created_at.desc())
    transcripts, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(transcripts, total=total, limit=limit, offset=offset)


@app.get("/transcripts/{transcript_id}")
def get_transcript(transcript_id: str, db: Session = Depends(get_db)):
    """
    Get a transcript by ID.

    Args:
        transcript_id: The ID of the transcript
        db: Database session

    Returns:
        The transcript object
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript


@app.get("/transcripts/{transcript_id}/export")
def export_transcript(
    transcript_id: str,
    export_format: Literal["txt", "srt", "vtt", "json", "ass", "review_package"] = Query(default="txt", alias="format"),
    include_timestamps: bool = Query(default=True),
    include_speakers: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """
    Download a transcript export generated by the backend.
    """
    started_at = time.perf_counter()
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    base_filename = (
        transcript.video.filename
        if transcript.video and transcript.video.filename
        else f"transcript-{transcript.id}"
    )
    transcript_segments = (
        build_segments_snapshot_from_rows(list(transcript.segment_rows))
        if transcript.segment_rows
        else transcript.segments
    )
    speaker_aliases = (
        build_speaker_alias_snapshot(list(transcript.speakers))
        if transcript.speakers
        else transcript.speaker_aliases
    )

    if export_format == "review_package":
        summaries = (
            db.query(Summary)
            .filter(Summary.transcript_id == transcript_id)
            .order_by(Summary.created_at.desc())
            .all()
        )
        translated_transcripts = (
            db.query(TranslatedTranscript)
            .filter(TranslatedTranscript.transcript_id == transcript_id)
            .order_by(TranslatedTranscript.created_at.desc())
            .all()
        )
        comments = (
            db.query(TranscriptComment)
            .filter(TranscriptComment.transcript_id == transcript_id)
            .order_by(TranscriptComment.created_at.desc())
            .all()
        )
        revisions = (
            db.query(TranscriptRevision)
            .filter(TranscriptRevision.transcript_id == transcript_id)
            .order_by(TranscriptRevision.revision_number.desc(), TranscriptRevision.created_at.desc())
            .all()
        )
        archive_bytes = build_transcript_review_package(
            base_filename=base_filename,
            transcript=transcript,
            summaries=summaries,
            translated_transcripts=translated_transcripts,
            comments=comments,
            revisions=revisions,
        )
        filename_root, _filename_ext = os.path.splitext(base_filename)
        response = build_archive_response(
            archive_bytes=archive_bytes,
            archive_name=f"{filename_root or 'transcript'}-review-package.zip",
        )
        record_metric_event(
            "export_time_seconds",
            time.perf_counter() - started_at,
            source="api",
            labels={"export_format": export_format, "transcript_kind": "source"},
        )
        return response

    export_payload = build_transcript_export_payload(
        content=transcript.content,
        segments=transcript_segments,
        speaker_aliases=speaker_aliases,
        extra={
            "transcript_id": str(transcript.id),
            "video_id": str(transcript.video_id) if transcript.video_id else None,
            "language_code": transcript.language_code,
            "review_status": transcript.review_status,
            "review_assignee": transcript.review_assignee,
        },
    )
    export_content = build_transcript_export_content(
        transcript.content,
        transcript_segments,
        export_format=export_format,
        include_timestamps=include_timestamps,
        include_speakers=include_speakers,
        speaker_aliases=speaker_aliases,
        export_payload=export_payload,
    )
    response = build_export_response(
        base_filename=base_filename,
        export_content=export_content,
        export_format=export_format,
    )
    record_metric_event(
        "export_time_seconds",
        time.perf_counter() - started_at,
        source="api",
        labels={"export_format": export_format, "transcript_kind": "source"},
    )
    return response


@app.get("/transcripts/{transcript_id}/revisions", response_model=List[TranscriptRevisionResponse])
def list_transcript_revisions(transcript_id: str, db: Session = Depends(get_db)):
    """
    List transcript revisions in descending revision order.
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    return (
        db.query(TranscriptRevision)
        .filter(TranscriptRevision.transcript_id == transcript_id)
        .order_by(TranscriptRevision.revision_number.desc(), TranscriptRevision.created_at.desc())
        .all()
    )


@app.post("/transcripts/{transcript_id}/revisions/{revision_id}/restore", response_model=TranscriptResponse)
async def restore_transcript_revision(
    transcript_id: str,
    revision_id: str,
    db: Session = Depends(get_db),
):
    """
    Restore a transcript to a previous revision snapshot.
    """
    transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    revision = (
        db.query(TranscriptRevision)
        .filter(
            TranscriptRevision.id == revision_id,
            TranscriptRevision.transcript_id == transcript_id,
        )
        .first()
    )
    if not revision:
        raise HTTPException(status_code=404, detail="Transcript revision not found")

    transcript.content = revision.content
    transcript.segments = revision.segments
    transcript.speaker_aliases = normalize_speaker_aliases(revision.speaker_aliases)
    sync_transcript_segment_rows(db, transcript)
    sync_transcript_speaker_rows(db, transcript)
    create_transcript_revision(
        db,
        transcript,
        reason=f"restore_revision_{revision.revision_number}",
    )
    sync_transcript_search_rows(db, transcript)
    db.commit()
    db.refresh(transcript)

    await publish_live_update(
        EVENT_TRANSCRIPT_UPDATED,
        transcript_id=str(transcript.id),
        video_id=str(transcript.video_id) if transcript.video_id else None,
    )

    return transcript


@app.get("/summaries/", response_model=PaginatedResponse[SummaryResponse])
def list_summaries(
    transcript_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List all summaries, optionally filtered by transcript ID.

    Args:
        transcript_id: Optional transcript ID to filter by
        db: Database session

    Returns:
        List of summaries
    """
    query = db.query(Summary)
    if transcript_id:
        query = query.filter(Summary.transcript_id == transcript_id)
    query = query.order_by(Summary.created_at.desc())
    summaries, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(
        [build_summary_response(summary) for summary in summaries],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.get("/summaries/{summary_id}")
def get_summary(summary_id: str, db: Session = Depends(get_db)):
    """
    Get a summary by ID.

    Args:
        summary_id: The ID of the summary
        db: Database session

    Returns:
        The summary object
    """
    summary = db.query(Summary).filter(Summary.id == summary_id).first()
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return build_summary_response(summary)


@app.post("/translation-jobs/", response_model=TranslationJobResponse)
async def create_translation_job_endpoint(job_data: TranslationJobCreate, db: Session = Depends(get_db)):
    """
    Create a new translation job.

    Args:
        job_data: The job data
        db: Database session

    Returns:
        The created translation job
    """
    logger.info(f"Creating translation job for transcript: {job_data.transcript_id} to {job_data.target_language}")

    # Check if the transcript exists
    transcript = db.query(Transcript).filter(Transcript.id == job_data.transcript_id).first()
    if not transcript:
        raise HTTPException(status_code=404, detail=f"Transcript not found: {job_data.transcript_id}")

    style_guide = normalize_translation_style_guide(job_data.style_guide)
    glossary_terms = normalize_glossary_terms(job_data.glossary_terms)

    try:
        unified_job = create_translation_job_for_transcript(
            job_data.transcript_id,
            job_data.target_language,
            job_data.source_language,
            style_guide=style_guide,
            glossary_terms=glossary_terms,
        )
    except ValueError as error:
        raise translate_job_domain_error(error) from error

    return get_legacy_job_or_404(
        db,
        job_type="translation",
        legacy_job_id=str(unified_job["legacy_job_id"]),
    )


@app.post("/translation-jobs/claim", response_model=Optional[TranslationJobResponse])
async def claim_translation_job(request_data: LeaseWorkerRequest, db: Session = Depends(get_db)):
    """Atomically claim the next available translation job."""
    unified_job = claim_next_translation_job(request_data.worker_id)
    if not unified_job:
        return None

    return get_legacy_job_or_404(
        db,
        job_type="translation",
        legacy_job_id=str(unified_job["legacy_job_id"]),
    )


@app.post("/translation-jobs/{job_id}/heartbeat", response_model=TranslationJobResponse)
async def heartbeat_translation_job(job_id: str, request_data: LeaseWorkerRequest, db: Session = Depends(get_db)):
    """Refresh a translation job lease for the owning worker."""
    try:
        heartbeat_legacy_job("translation", job_id, request_data.worker_id)
        job = get_legacy_job_or_404(db, job_type="translation", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.get("/translation-jobs", response_model=PaginatedResponse[TranslationJobResponse])
async def get_translation_jobs(
    status: Optional[str] = None,
    transcript_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    Get all translation jobs, optionally filtered by status and transcript_id.
    Used by the translation worker and frontend.

    Args:
        status: Optional status to filter by
        transcript_id: Optional transcript ID to filter by
        db: Database session

    Returns:
        List of translation jobs
    """
    query = db.query(TranslationJob)

    if status:
        query = query.filter(TranslationJob.status == status)

    if transcript_id:
        query = query.filter(TranslationJob.transcript_id == transcript_id)

    query = query.order_by(TranslationJob.created_at.desc())
    jobs, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@app.get("/translation-jobs/{job_id}", response_model=TranslationJobResponse)
async def get_translation_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get a translation job by ID.

    Args:
        job_id: The ID of the job
        db: Database session

    Returns:
        The translation job
    """
    job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Translation job not found: {job_id}")
    return job


@app.get("/jobs", response_model=PaginatedResponse[UnifiedJobResponse])
def list_unified_jobs(
    job_type: Optional[Literal["summarization", "transcription", "translation"]] = None,
    status: Optional[str] = None,
    subject_type: Optional[Literal["transcript", "video"]] = None,
    subject_id: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List canonical orchestration jobs across all legacy job tables.
    """
    query = db.query(UnifiedJob)
    if job_type:
        query = query.filter(UnifiedJob.job_type == job_type)
    if status:
        query = query.filter(UnifiedJob.status == status)
    if subject_type:
        query = query.filter(UnifiedJob.subject_type == subject_type)
    if subject_id:
        query = query.filter(UnifiedJob.subject_id == subject_id)

    query = query.order_by(UnifiedJob.created_at.desc(), UnifiedJob.id.desc())
    jobs, total = paginate_query(query, limit=limit, offset=offset)
    return build_paginated_response(jobs, total=total, limit=limit, offset=offset)


@app.get("/jobs/{job_id}", response_model=UnifiedJobResponse)
def get_unified_job(job_id: str, db: Session = Depends(get_db)):
    """
    Get a canonical orchestration job by ID.
    """
    job = db.query(UnifiedJob).filter(UnifiedJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/jobs/{job_id}/attempts", response_model=List[JobAttemptResponse])
def list_job_attempts(job_id: str, db: Session = Depends(get_db)):
    """
    List attempts for a canonical orchestration job.
    """
    job = db.query(UnifiedJob).filter(UnifiedJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return (
        db.query(JobAttempt)
        .filter(JobAttempt.job_id == job_id)
        .order_by(JobAttempt.attempt_number.desc(), JobAttempt.created_at.desc())
        .all()
    )


@app.post("/jobs/{job_id}/cancel", response_model=UnifiedJobResponse)
def cancel_unified_job(job_id: str):
    """
    Request cancellation for a unified orchestration job.
    """
    try:
        return request_job_cancellation(job_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error


@app.post("/jobs/{job_id}/retry", response_model=UnifiedJobResponse)
def retry_unified_job(job_id: str):
    """
    Retry a failed or cancelled unified orchestration job.
    """
    try:
        return retry_job(job_id)
    except ValueError as error:
        raise translate_job_domain_error(error) from error


@app.post("/translation-jobs/{job_id}/complete", response_model=TranslationJobResponse)
async def complete_translation_job(job_id: str, update_data: TranslationJobUpdate, db: Session = Depends(get_db)):
    """
    Mark a translation job as completed.
    Used by the translation worker.

    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session

    Returns:
        The updated translation job
    """
    try:
        complete_legacy_job(
            "translation",
            job_id,
            update_data.worker_id,
            processing_time=update_data.processing_time_seconds,
            error_details=update_data.error_details,
        )
        job = get_legacy_job_or_404(db, job_type="translation", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.post("/translation-jobs/{job_id}/fail", response_model=TranslationJobResponse)
async def fail_translation_job(job_id: str, update_data: TranslationJobUpdate, db: Session = Depends(get_db)):
    """
    Mark a translation job as failed.
    Used by the translation worker.

    Args:
        job_id: The ID of the job
        update_data: The update data
        db: Database session

    Returns:
        The updated translation job
    """
    try:
        fail_legacy_job(
            "translation",
            job_id,
            update_data.worker_id,
            error_details=update_data.error_details,
        )
        job = get_legacy_job_or_404(db, job_type="translation", legacy_job_id=job_id)
    except JobLeaseOwnershipError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ValueError as error:
        raise translate_job_domain_error(error) from error
    return job


@app.post("/translated-transcripts/", response_model=TranslatedTranscriptResponse)
async def create_translated_transcript(transcript_data: TranslatedTranscriptCreate, db: Session = Depends(get_db)):
    """
    Create a new translated transcript.
    Used by the translation worker.

    Args:
        transcript_data: The translated transcript data
        db: Database session

    Returns:
        The created translated transcript
    """
    logger.info(
        f"Creating translated transcript for transcript: {transcript_data.transcript_id} in {transcript_data.language}"
    )

    # Check if the transcript exists
    transcript = db.query(Transcript).filter(Transcript.id == transcript_data.transcript_id).first()
    if not transcript:
        raise HTTPException(
            status_code=404,
            detail=f"Transcript not found: {transcript_data.transcript_id}",
        )

    translated_transcript = (
        db.query(TranslatedTranscript)
        .filter(TranslatedTranscript.transcript_id == transcript_data.transcript_id)
        .filter(TranslatedTranscript.language == transcript_data.language)
        .order_by(TranslatedTranscript.created_at.desc())
        .first()
    )

    is_existing_translation = translated_transcript is not None
    if translated_transcript:
        translated_transcript.content = transcript_data.content
        translated_transcript.segments = transcript_data.segments
        translated_transcript.style_guide = normalize_translation_style_guide(
            transcript_data.style_guide
        )
        translated_transcript.glossary_terms = transcript_data.glossary_terms or []
        translated_transcript.qa_metrics = transcript_data.qa_metrics
        translated_transcript.status = transcript_data.status
    else:
        translated_transcript = TranslatedTranscript(
            transcript_id=transcript_data.transcript_id,
            language=transcript_data.language,
            content=transcript_data.content,
            segments=transcript_data.segments,
            style_guide=normalize_translation_style_guide(transcript_data.style_guide),
            glossary_terms=transcript_data.glossary_terms or [],
            qa_metrics=transcript_data.qa_metrics,
            status=transcript_data.status,
        )
        db.add(translated_transcript)

    db.flush()
    sync_translated_transcript_segment_rows(db, translated_transcript)
    sync_translated_transcript_localization_rows(db, translated_transcript)
    db.commit()
    db.refresh(translated_transcript)

    if is_existing_translation:
        await publish_live_update(
            EVENT_TRANSLATED_TRANSCRIPT_UPDATED,
            language=translated_transcript.language,
            transcript_id=str(translated_transcript.transcript_id),
            translated_transcript_id=str(translated_transcript.id),
        )
    else:
        await publish_live_update(
            EVENT_TRANSLATION_CREATED,
            language=translated_transcript.language,
            transcript_id=str(translated_transcript.transcript_id),
            translated_transcript_id=str(translated_transcript.id),
        )

    return translated_transcript


@app.get("/translated-transcripts/", response_model=PaginatedResponse[TranslatedTranscriptResponse])
def list_translated_transcripts(
    transcript_id: Optional[str] = None,
    language: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """
    List all translated transcripts, optionally filtered by transcript ID and/or language.

    Args:
        transcript_id: Optional transcript ID to filter by
        language: Optional language code to filter by
        db: Database session

    Returns:
        List of translated transcripts
    """
    query = db.query(TranslatedTranscript)

    if transcript_id:
        query = query.filter(TranslatedTranscript.transcript_id == transcript_id)

    if language:
        query = query.filter(TranslatedTranscript.language == language)

    translated_transcripts = query.order_by(TranslatedTranscript.created_at.desc()).all()

    if language:
        paginated_items, total = paginate_items(translated_transcripts, limit=limit, offset=offset)
        return build_paginated_response(paginated_items, total=total, limit=limit, offset=offset)

    latest_translations_by_language = {}
    for translated_transcript in translated_transcripts:
        if translated_transcript.language not in latest_translations_by_language:
            latest_translations_by_language[translated_transcript.language] = translated_transcript

    latest_translations = list(latest_translations_by_language.values())
    paginated_items, total = paginate_items(latest_translations, limit=limit, offset=offset)
    return build_paginated_response(paginated_items, total=total, limit=limit, offset=offset)


@app.get("/translated-transcripts/{translated_transcript_id}")
def get_translated_transcript(translated_transcript_id: str, db: Session = Depends(get_db)):
    """
    Get a translated transcript by ID.
    """
    translated_transcript = (
        db.query(TranslatedTranscript).filter(TranslatedTranscript.id == translated_transcript_id).first()
    )
    if not translated_transcript:
        raise HTTPException(status_code=404, detail="Translated transcript not found")
    return translated_transcript


@app.get("/translated-transcripts/{translated_transcript_id}/export")
def export_translated_transcript(
    translated_transcript_id: str,
    export_format: Literal["txt", "srt", "vtt", "json", "ass"] = Query(default="txt", alias="format"),
    include_timestamps: bool = Query(default=True),
    include_speakers: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    """
    Download a translated transcript export generated by the backend.
    """
    started_at = time.perf_counter()
    translated_transcript = (
        db.query(TranslatedTranscript).filter(TranslatedTranscript.id == translated_transcript_id).first()
    )
    if not translated_transcript:
        raise HTTPException(status_code=404, detail="Translated transcript not found")

    source_filename = (
        translated_transcript.transcript.video.filename
        if translated_transcript.transcript
        and translated_transcript.transcript.video
        and translated_transcript.transcript.video.filename
        else f"translated-transcript-{translated_transcript.id}"
    )
    filename_root, _filename_ext = os.path.splitext(source_filename)
    translated_segments = (
        build_segments_snapshot_from_rows(list(translated_transcript.segment_rows))
        if translated_transcript.segment_rows
        else translated_transcript.segments
    )
    source_speaker_aliases = (
        build_speaker_alias_snapshot(list(translated_transcript.transcript.speakers))
        if translated_transcript.transcript and translated_transcript.transcript.speakers
        else (
            translated_transcript.transcript.speaker_aliases
            if translated_transcript.transcript
            else None
        )
    )
    export_payload = build_transcript_export_payload(
        content=translated_transcript.content,
        segments=translated_segments,
        speaker_aliases=source_speaker_aliases,
        extra={
            "translated_transcript_id": str(translated_transcript.id),
            "transcript_id": str(translated_transcript.transcript_id),
            "language": translated_transcript.language,
            "style_guide": translated_transcript.style_guide,
            "glossary_terms": translated_transcript.glossary_terms or [],
            "qa_metrics": translated_transcript.qa_metrics or {},
            "status": translated_transcript.status,
        },
    )
    export_content = build_transcript_export_content(
        translated_transcript.content,
        translated_segments,
        export_format=export_format,
        include_timestamps=include_timestamps,
        include_speakers=include_speakers,
        speaker_aliases=source_speaker_aliases,
        export_payload=export_payload,
    )
    response = build_export_response(
        base_filename=f"{filename_root}-{translated_transcript.language}",
        export_content=export_content,
        export_format=export_format,
    )
    record_metric_event(
        "export_time_seconds",
        time.perf_counter() - started_at,
        source="api",
        labels={
            "export_format": export_format,
            "transcript_kind": "translation",
            "language": translated_transcript.language,
        },
    )
    return response


@app.put("/translated-transcripts/{translated_transcript_id}/segments", response_model=TranslatedTranscriptResponse)
async def update_translated_transcript_segments(translated_transcript_id: str, update_data: TranscriptSegmentsUpdate, db: Session = Depends(get_db)):
    """
    Update the segments (and optionally the full text content) of a translated transcript.
    Used by the frontend for interactive transcript editing.
    """
    translated_transcript = db.query(TranslatedTranscript).filter(TranslatedTranscript.id == translated_transcript_id).first()
    if not translated_transcript:
        raise HTTPException(status_code=404, detail=f"Translated transcript not found: {translated_transcript_id}")

    translated_transcript.segments = update_data.segments
    if update_data.content is not None:
        translated_transcript.content = update_data.content

    sync_translated_transcript_segment_rows(db, translated_transcript)
    db.commit()
    db.refresh(translated_transcript)

    await publish_live_update(
        EVENT_TRANSLATED_TRANSCRIPT_UPDATED,
        language=translated_transcript.language,
        transcript_id=str(translated_transcript.transcript_id),
        translated_transcript_id=str(translated_transcript.id),
    )

    return translated_transcript

@app.get("/search", response_model=PaginatedResponse[SearchResultResponse])
async def search_transcripts(
    q: str,
    language_code: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    review_status: Optional[Literal["draft", "in_review", "approved", "needs_changes"]] = None,
    speaker: Optional[str] = None,
    video_id: Optional[str] = None,
    video_title: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Search across all transcript segments for a given query string.
    """
    started_at = time.perf_counter()
    results = search_transcript_segments(
        db,
        q,
        language_code=language_code,
        limit=limit,
        offset=offset,
        review_status=review_status,
        speaker=speaker,
        video_id=video_id,
        video_title=video_title,
    )
    record_metric_event(
        "search_latency_seconds",
        time.perf_counter() - started_at,
        source="api",
        labels={
            "language_code": language_code or "any",
            "review_status": review_status or "any",
            "speaker_filter": "1" if speaker else "0",
            "video_filter": "1" if video_id else "0",
        },
    )
    return results
