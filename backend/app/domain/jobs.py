from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from backend.app.domain.job_queue import (
    JobLeaseOwnershipError,
    create_summarization_job as create_summarization_job_row,
    create_transcription_job as create_transcription_job_row,
    create_translation_job as create_translation_job_row,
)
from backend.app.persistence.database import SessionLocal
from backend.app.persistence.models import (
    JobAttempt,
    SummarizationJob,
    Transcript,
    TranscriptionJob,
    TranslationJob,
    UnifiedJob,
    Video,
)
from backend.app.domain.events import publish_job_live_update_sync
from backend.app.runtime.config import JOB_LEASE_DURATION_SECONDS
from backend.app.runtime.metrics import record_metric_event


logger = logging.getLogger("backend.domain.jobs")

JOB_STATUS_PENDING = "pending"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
JOB_STATUS_CANCEL_REQUESTED = "cancel_requested"
JOB_STATUS_CANCELLED = "cancelled"
ATTEMPT_STATUS_CANCELLED = "cancelled"
ATTEMPT_STATUS_EXPIRED = "expired"

JOB_TYPE_SPECS: dict[str, dict[str, Any]] = {
    "transcription": {
        "legacy_model": TranscriptionJob,
        "legacy_table": "transcription_jobs",
        "subject_type": "video",
        "subject_key": "video_id",
    },
    "summarization": {
        "legacy_model": SummarizationJob,
        "legacy_table": "summarization_jobs",
        "subject_type": "transcript",
        "subject_key": "transcript_id",
    },
    "translation": {
        "legacy_model": TranslationJob,
        "legacy_table": "translation_jobs",
        "subject_type": "transcript",
        "subject_key": "transcript_id",
    },
}


class JobCancellationRequestedError(RuntimeError):
    """Raised when a worker should stop because cancellation was requested."""


def _lease_expiration() -> datetime:
    return datetime.utcnow() + timedelta(seconds=JOB_LEASE_DURATION_SECONDS)


def _get_job_spec(job_type: str) -> dict[str, Any]:
    if job_type not in JOB_TYPE_SPECS:
        raise ValueError(f"Unsupported job type: {job_type}")
    return JOB_TYPE_SPECS[job_type]


def _get_job_type_for_legacy_model(model: type[Any]) -> str:
    for job_type, spec in JOB_TYPE_SPECS.items():
        if spec["legacy_model"] is model:
            return job_type
    raise ValueError(f"Unsupported legacy model: {model}")


def _build_unified_payload_from_legacy(job_type: str, legacy_job: Any) -> Dict[str, Any]:
    spec = _get_job_spec(job_type)
    payload: Dict[str, Any] = {
        spec["subject_key"]: str(getattr(legacy_job, spec["subject_key"])),
    }

    if job_type == "summarization":
        if legacy_job.content_profile:
            payload["content_profile"] = legacy_job.content_profile
    elif job_type == "translation":
        payload.update(
            {
                "source_language": legacy_job.source_language,
                "target_language": legacy_job.target_language,
                "style_guide": legacy_job.style_guide,
                "glossary_terms": legacy_job.glossary_terms or [],
            }
        )

    return payload


def _get_legacy_job_for_unified_job(unified_job: UnifiedJob, db: Session) -> Any:
    spec = _get_job_spec(unified_job.job_type)
    legacy_model = spec["legacy_model"]
    legacy_job = (
        db.query(legacy_model)
        .filter(legacy_model.id == unified_job.legacy_job_id)
        .first()
    )
    if not legacy_job:
        raise ValueError(
            f"Legacy {unified_job.job_type} job not found for unified job {unified_job.id}"
        )
    return legacy_job


def _get_unified_job(db: Session, job_id: str, *, job_type: Optional[str] = None) -> UnifiedJob:
    query = db.query(UnifiedJob).filter(UnifiedJob.id == job_id)
    if job_type:
        query = query.filter(UnifiedJob.job_type == job_type)

    unified_job = query.first()
    if not unified_job:
        raise ValueError(f"Unified job not found: {job_id}")
    return unified_job


def _get_unified_job_for_legacy_id(db: Session, job_type: str, legacy_job_id: str) -> UnifiedJob:
    unified_job = (
        db.query(UnifiedJob)
        .filter(UnifiedJob.job_type == job_type)
        .filter(UnifiedJob.legacy_job_id == legacy_job_id)
        .first()
    )
    if not unified_job:
        raise ValueError(f"Unified {job_type} job not found for legacy id: {legacy_job_id}")
    return unified_job


def _sync_unified_from_legacy(unified_job: UnifiedJob, legacy_job: Any, *, job_type: str) -> None:
    spec = _get_job_spec(job_type)
    unified_job.job_type = job_type
    unified_job.subject_type = spec["subject_type"]
    unified_job.subject_id = str(getattr(legacy_job, spec["subject_key"]))
    unified_job.payload = _build_unified_payload_from_legacy(job_type, legacy_job)
    unified_job.status = legacy_job.status
    unified_job.worker_id = legacy_job.worker_id
    unified_job.lease_expires_at = legacy_job.lease_expires_at
    unified_job.created_at = legacy_job.created_at
    unified_job.started_at = legacy_job.started_at
    unified_job.completed_at = legacy_job.completed_at
    unified_job.processing_time_seconds = legacy_job.processing_time_seconds
    unified_job.error_details = legacy_job.error_details


def _sync_legacy_from_unified(unified_job: UnifiedJob, legacy_job: Any) -> None:
    legacy_job.status = unified_job.status
    legacy_job.worker_id = unified_job.worker_id
    legacy_job.lease_expires_at = unified_job.lease_expires_at
    legacy_job.started_at = unified_job.started_at
    legacy_job.completed_at = unified_job.completed_at
    legacy_job.processing_time_seconds = unified_job.processing_time_seconds
    legacy_job.error_details = unified_job.error_details


def _close_active_attempts(
    unified_job: UnifiedJob,
    db: Session,
    *,
    now: datetime,
    status: str,
    error_message: str,
) -> None:
    active_attempts = (
        db.query(JobAttempt)
        .filter(
            JobAttempt.job_id == unified_job.id,
            JobAttempt.completed_at.is_(None),
        )
        .all()
    )
    for attempt in active_attempts:
        attempt.status = status
        attempt.completed_at = now
        attempt.error_details = {"error": error_message}


def _start_attempt(unified_job: UnifiedJob, worker_id: str, db: Session, *, now: datetime) -> None:
    _close_active_attempts(
        unified_job,
        db,
        now=now,
        status=ATTEMPT_STATUS_EXPIRED,
        error_message="Lease expired before completion",
    )
    next_attempt_number = int(unified_job.attempt_count or 0) + 1
    unified_job.attempt_count = next_attempt_number
    db.add(
        JobAttempt(
            job_id=unified_job.id,
            attempt_number=next_attempt_number,
            worker_id=worker_id,
            status=JOB_STATUS_PROCESSING,
            started_at=now,
            created_at=now,
        )
    )


def _get_active_attempt(unified_job: UnifiedJob, db: Session) -> Optional[JobAttempt]:
    return (
        db.query(JobAttempt)
        .filter(
            JobAttempt.job_id == unified_job.id,
            JobAttempt.completed_at.is_(None),
        )
        .order_by(JobAttempt.attempt_number.desc())
        .first()
    )


def _ensure_worker_owns_job(unified_job: UnifiedJob, worker_id: str) -> None:
    if unified_job.worker_id != worker_id or unified_job.status not in {
        JOB_STATUS_PROCESSING,
        JOB_STATUS_CANCEL_REQUESTED,
    }:
        raise JobLeaseOwnershipError(
            f"Worker {worker_id} does not own job {unified_job.id}. "
            f"Current worker: {unified_job.worker_id}, status: {unified_job.status}"
        )


def _finalize_expired_cancellations(job_type: str, db: Session, *, now: datetime) -> None:
    expired_jobs = (
        db.query(UnifiedJob)
        .filter(
            UnifiedJob.job_type == job_type,
            UnifiedJob.status == JOB_STATUS_CANCEL_REQUESTED,
            UnifiedJob.lease_expires_at.isnot(None),
            UnifiedJob.lease_expires_at < now,
        )
        .all()
    )
    for unified_job in expired_jobs:
        legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
        unified_job.status = JOB_STATUS_CANCELLED
        unified_job.completed_at = now
        unified_job.worker_id = None
        unified_job.lease_expires_at = None
        unified_job.processing_time_seconds = unified_job.processing_time_seconds
        unified_job.error_details = {
            **(unified_job.error_details or {}),
            "error": "Job cancelled after worker lease expired",
        }
        _close_active_attempts(
            unified_job,
            db,
            now=now,
            status=ATTEMPT_STATUS_CANCELLED,
            error_message="Cancellation completed after worker lease expired",
        )
        _sync_legacy_from_unified(unified_job, legacy_job)


def _claimable_job_query(job_type: str, db: Session, *, now: datetime):
    return (
        db.query(UnifiedJob)
        .filter(
            UnifiedJob.job_type == job_type,
            or_(
                UnifiedJob.status == JOB_STATUS_PENDING,
                and_(
                    UnifiedJob.status == JOB_STATUS_PROCESSING,
                    UnifiedJob.lease_expires_at.isnot(None),
                    UnifiedJob.lease_expires_at < now,
                ),
            ),
        )
        .order_by(UnifiedJob.priority.asc(), UnifiedJob.created_at.asc(), UnifiedJob.id.asc())
    )


def serialize_job(unified_job: UnifiedJob) -> Dict[str, Any]:
    payload = dict(unified_job.payload or {})
    serialized_job: Dict[str, Any] = {
        "id": str(unified_job.id),
        "legacy_job_id": str(unified_job.legacy_job_id),
        "legacy_job_table": unified_job.legacy_job_table,
        "job_type": unified_job.job_type,
        "subject_type": unified_job.subject_type,
        "subject_id": unified_job.subject_id,
        "status": unified_job.status,
        "priority": int(unified_job.priority or 100),
        "payload": payload,
        "progress": unified_job.progress,
        "attempt_count": int(unified_job.attempt_count or 0),
        "created_at": unified_job.created_at,
        "started_at": unified_job.started_at,
        "completed_at": unified_job.completed_at,
        "processing_time_seconds": unified_job.processing_time_seconds,
        "error_details": unified_job.error_details,
        "worker_id": unified_job.worker_id,
        "lease_expires_at": unified_job.lease_expires_at,
    }
    serialized_job.update(payload)
    return serialized_job


def _publish_job_update(unified_job: UnifiedJob) -> None:
    subject_payload: Dict[str, Optional[str]] = {
        "video_id": None,
        "transcript_id": None,
    }
    if unified_job.subject_type == "video":
        subject_payload["video_id"] = unified_job.subject_id
    elif unified_job.subject_type == "transcript":
        subject_payload["transcript_id"] = unified_job.subject_id

    publish_job_live_update_sync(
        unified_job.job_type,
        str(unified_job.id),
        unified_job.status,
        video_id=subject_payload["video_id"],
        transcript_id=subject_payload["transcript_id"],
        worker_id=unified_job.worker_id,
        lease_expires_at=unified_job.lease_expires_at,
        progress=unified_job.progress,
        attempt_count=int(unified_job.attempt_count or 0),
    )


def claim_next_job(job_type: str, worker_id: str) -> Optional[Dict[str, Any]]:
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        _finalize_expired_cancellations(job_type, db, now=now)
        unified_job = _claimable_job_query(job_type, db, now=now).with_for_update(skip_locked=True).first()
        if not unified_job:
            db.commit()
            return None

        legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
        unified_job.status = JOB_STATUS_PROCESSING
        unified_job.worker_id = worker_id
        unified_job.started_at = now
        unified_job.completed_at = None
        unified_job.lease_expires_at = _lease_expiration()
        unified_job.progress = 0.0
        unified_job.error_details = None
        _sync_unified_from_legacy(unified_job, legacy_job, job_type=job_type)
        unified_job.status = JOB_STATUS_PROCESSING
        unified_job.worker_id = worker_id
        unified_job.started_at = now
        unified_job.completed_at = None
        unified_job.lease_expires_at = _lease_expiration()
        unified_job.progress = 0.0
        unified_job.error_details = None
        _start_attempt(unified_job, worker_id, db, now=now)
        _sync_legacy_from_unified(unified_job, legacy_job)
        db.commit()
        db.refresh(unified_job)
        queue_wait_seconds = max((now - unified_job.created_at).total_seconds(), 0.0)
        record_metric_event(
            "job_queue_wait_seconds",
            queue_wait_seconds,
            source="orchestration",
            labels={"job_type": job_type},
        )
        record_metric_event(
            "job_claims_total",
            1,
            source="orchestration",
            labels={"job_type": job_type},
        )
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def get_job(job_id: str, *, job_type: Optional[str] = None) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id, job_type=job_type)
        return serialize_job(unified_job)
    finally:
        db.close()


def heartbeat_job(job_id: str, worker_id: str, *, job_type: Optional[str] = None) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id, job_type=job_type)
        _ensure_worker_owns_job(unified_job, worker_id)
        unified_job.lease_expires_at = _lease_expiration()
        legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
        _sync_legacy_from_unified(unified_job, legacy_job)
        db.commit()
        db.refresh(unified_job)
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def update_job_progress(
    job_id: str,
    worker_id: str,
    progress: float,
    *,
    error_details: Optional[Dict[str, Any]] = None,
    job_type: Optional[str] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id, job_type=job_type)
        _ensure_worker_owns_job(unified_job, worker_id)
        unified_job.progress = max(0.0, min(float(progress), 1.0))
        if error_details is not None:
            unified_job.error_details = error_details
        db.commit()
        db.refresh(unified_job)
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def ensure_job_not_cancelled(job_id: str, worker_id: str, *, job_type: Optional[str] = None) -> None:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id, job_type=job_type)
        _ensure_worker_owns_job(unified_job, worker_id)
        if unified_job.status in {JOB_STATUS_CANCEL_REQUESTED, JOB_STATUS_CANCELLED}:
            raise JobCancellationRequestedError(
                f"Cancellation requested for job {job_id}"
            )
    finally:
        db.close()


def complete_job(
    job_id: str,
    worker_id: str,
    *,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
    job_type: Optional[str] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id, job_type=job_type)
        _ensure_worker_owns_job(unified_job, worker_id)

        now = datetime.utcnow()
        if unified_job.status == JOB_STATUS_CANCEL_REQUESTED:
            unified_job.status = JOB_STATUS_CANCELLED
            unified_job.completed_at = now
            unified_job.error_details = {
                **(error_details or {}),
                "error": "Job cancelled by request",
            }
            active_attempt = _get_active_attempt(unified_job, db)
            if active_attempt:
                active_attempt.status = ATTEMPT_STATUS_CANCELLED
                active_attempt.completed_at = now
                active_attempt.processing_time_seconds = processing_time
                active_attempt.error_details = {"error": "Job cancelled by request"}
        else:
            unified_job.status = JOB_STATUS_COMPLETED
            unified_job.completed_at = now
            active_attempt = _get_active_attempt(unified_job, db)
            if active_attempt:
                active_attempt.status = JOB_STATUS_COMPLETED
                active_attempt.completed_at = now
                active_attempt.processing_time_seconds = processing_time

        unified_job.processing_time_seconds = processing_time
        unified_job.progress = 1.0 if unified_job.status == JOB_STATUS_COMPLETED else unified_job.progress
        if error_details is not None and unified_job.status == JOB_STATUS_COMPLETED:
            unified_job.error_details = error_details
        unified_job.worker_id = None
        unified_job.lease_expires_at = None

        legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
        _sync_legacy_from_unified(unified_job, legacy_job)
        db.commit()
        db.refresh(unified_job)
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def fail_job(
    job_id: str,
    worker_id: str,
    *,
    error_details: Optional[Dict[str, Any]] = None,
    job_type: Optional[str] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id, job_type=job_type)
        _ensure_worker_owns_job(unified_job, worker_id)
        now = datetime.utcnow()
        unified_job.status = JOB_STATUS_FAILED
        unified_job.completed_at = now
        unified_job.error_details = error_details or {"error": "Unknown error"}
        unified_job.worker_id = None
        unified_job.lease_expires_at = None
        active_attempt = _get_active_attempt(unified_job, db)
        if active_attempt:
            active_attempt.status = JOB_STATUS_FAILED
            active_attempt.completed_at = now
            active_attempt.error_details = unified_job.error_details

        legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
        _sync_legacy_from_unified(unified_job, legacy_job)
        db.commit()
        db.refresh(unified_job)
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def request_job_cancellation(job_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id)
        now = datetime.utcnow()
        if unified_job.status == JOB_STATUS_PENDING:
            unified_job.status = JOB_STATUS_CANCELLED
            unified_job.completed_at = now
            unified_job.worker_id = None
            unified_job.lease_expires_at = None
            unified_job.error_details = {"error": "Job cancelled before processing"}
        elif unified_job.status in {JOB_STATUS_PROCESSING, JOB_STATUS_CANCEL_REQUESTED}:
            unified_job.status = JOB_STATUS_CANCEL_REQUESTED
            unified_job.error_details = {
                **(unified_job.error_details or {}),
                "error": "Cancellation requested",
            }
        else:
            raise ValueError(
                f"Job {job_id} cannot be cancelled from status {unified_job.status}"
            )

        legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
        _sync_legacy_from_unified(unified_job, legacy_job)
        db.commit()
        db.refresh(unified_job)
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def retry_job(job_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job(db, job_id)
        if unified_job.status not in {JOB_STATUS_FAILED, JOB_STATUS_CANCELLED}:
            raise ValueError(
                f"Job {job_id} is not retryable from status {unified_job.status}"
            )

        unified_job.status = JOB_STATUS_PENDING
        unified_job.worker_id = None
        unified_job.lease_expires_at = None
        unified_job.started_at = None
        unified_job.completed_at = None
        unified_job.processing_time_seconds = None
        unified_job.error_details = None
        unified_job.progress = 0.0

        legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
        _sync_legacy_from_unified(unified_job, legacy_job)
        db.commit()
        db.refresh(unified_job)
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def get_job_attempts(job_id: str) -> list[JobAttempt]:
    db = SessionLocal()
    try:
        _get_unified_job(db, job_id)
        return (
            db.query(JobAttempt)
            .filter(JobAttempt.job_id == job_id)
            .order_by(JobAttempt.attempt_number.desc(), JobAttempt.created_at.desc())
            .all()
        )
    finally:
        db.close()


def _get_created_unified_job_for_legacy(db: Session, job_type: str, legacy_job_id: str) -> UnifiedJob:
    unified_job = _get_unified_job_for_legacy_id(db, job_type, legacy_job_id)
    legacy_job = _get_legacy_job_for_unified_job(unified_job, db)
    _sync_unified_from_legacy(unified_job, legacy_job, job_type=job_type)
    db.commit()
    db.refresh(unified_job)
    return unified_job


def create_transcription_job_for_video(video_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        legacy_job = create_transcription_job_row(video_id, db)
        unified_job = _get_created_unified_job_for_legacy(db, "transcription", str(legacy_job.id))
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def create_summarization_job_for_transcript(
    transcript_id: str,
    *,
    content_profile: Optional[str] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            raise ValueError(f"Transcript not found: {transcript_id}")

        existing_job = (
            db.query(UnifiedJob)
            .filter(UnifiedJob.job_type == "summarization")
            .filter(UnifiedJob.subject_id == transcript_id)
            .filter(
                UnifiedJob.status.in_(
                    [JOB_STATUS_PENDING, JOB_STATUS_PROCESSING, JOB_STATUS_CANCEL_REQUESTED]
                )
            )
            .order_by(UnifiedJob.created_at.desc())
            .all()
        )
        for unified_job in existing_job:
            payload = unified_job.payload or {}
            if (payload.get("content_profile") or None) == (content_profile or None):
                return serialize_job(unified_job)

        legacy_job = create_summarization_job_row(
            transcript_id,
            db,
            content_profile=content_profile,
        )
        unified_job = _get_created_unified_job_for_legacy(db, "summarization", str(legacy_job.id))
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def create_translation_job_for_transcript(
    transcript_id: str,
    target_language: str,
    source_language: Optional[str] = None,
    *,
    style_guide: Optional[str] = None,
    glossary_terms: Optional[list[dict[str, str]]] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        transcript = db.query(Transcript).filter(Transcript.id == transcript_id).first()
        if not transcript:
            raise ValueError(f"Transcript not found: {transcript_id}")

        existing_job = (
            db.query(UnifiedJob)
            .filter(UnifiedJob.job_type == "translation")
            .filter(UnifiedJob.subject_id == transcript_id)
            .filter(UnifiedJob.status.in_([JOB_STATUS_PENDING, JOB_STATUS_PROCESSING, JOB_STATUS_CANCEL_REQUESTED]))
            .order_by(UnifiedJob.created_at.desc())
            .all()
        )
        for unified_job in existing_job:
            payload = unified_job.payload or {}
            if payload.get("target_language") != target_language:
                continue
            same_style_guide = (payload.get("style_guide") or None) == (style_guide or None)
            same_glossary_terms = (payload.get("glossary_terms") or []) == (glossary_terms or [])
            if same_style_guide and same_glossary_terms:
                return serialize_job(unified_job)

        legacy_job = create_translation_job_row(
            transcript_id,
            target_language,
            source_language,
            style_guide=style_guide,
            glossary_terms=glossary_terms,
            db=db,
        )
        unified_job = _get_created_unified_job_for_legacy(db, "translation", str(legacy_job.id))
        _publish_job_update(unified_job)
        return serialize_job(unified_job)
    finally:
        db.close()


def get_transcription_job(job_id: str) -> Dict[str, Any]:
    return get_job(job_id, job_type="transcription")


def claim_next_transcription_job(worker_id: str) -> Optional[Dict[str, Any]]:
    return claim_next_job("transcription", worker_id)


def heartbeat_transcription_job(job_id: str, worker_id: str) -> Dict[str, Any]:
    return heartbeat_job(job_id, worker_id, job_type="transcription")


def update_transcription_job_progress(
    job_id: str,
    worker_id: str,
    progress: float,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return update_job_progress(
        job_id,
        worker_id,
        progress,
        error_details=error_details,
        job_type="transcription",
    )


def ensure_transcription_job_not_cancelled(job_id: str, worker_id: str) -> None:
    ensure_job_not_cancelled(job_id, worker_id, job_type="transcription")


def complete_transcription_job(
    job_id: str,
    worker_id: str,
    *,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return complete_job(
        job_id,
        worker_id,
        processing_time=processing_time,
        error_details=error_details,
        job_type="transcription",
    )


def fail_transcription_job(
    job_id: str,
    worker_id: str,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return fail_job(
        job_id,
        worker_id,
        error_details=error_details,
        job_type="transcription",
    )


def get_summarization_job(job_id: str) -> Dict[str, Any]:
    return get_job(job_id, job_type="summarization")


def claim_next_summarization_job(worker_id: str) -> Optional[Dict[str, Any]]:
    return claim_next_job("summarization", worker_id)


def heartbeat_summarization_job(job_id: str, worker_id: str) -> Dict[str, Any]:
    return heartbeat_job(job_id, worker_id, job_type="summarization")


def update_summarization_job_progress(
    job_id: str,
    worker_id: str,
    progress: float,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return update_job_progress(
        job_id,
        worker_id,
        progress,
        error_details=error_details,
        job_type="summarization",
    )


def ensure_summarization_job_not_cancelled(job_id: str, worker_id: str) -> None:
    ensure_job_not_cancelled(job_id, worker_id, job_type="summarization")


def complete_summarization_job(
    job_id: str,
    worker_id: str,
    *,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return complete_job(
        job_id,
        worker_id,
        processing_time=processing_time,
        error_details=error_details,
        job_type="summarization",
    )


def fail_summarization_job(
    job_id: str,
    worker_id: str,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return fail_job(
        job_id,
        worker_id,
        error_details=error_details,
        job_type="summarization",
    )


def get_translation_job(job_id: str) -> Dict[str, Any]:
    return get_job(job_id, job_type="translation")


def claim_next_translation_job(worker_id: str) -> Optional[Dict[str, Any]]:
    return claim_next_job("translation", worker_id)


def heartbeat_translation_job(job_id: str, worker_id: str) -> Dict[str, Any]:
    return heartbeat_job(job_id, worker_id, job_type="translation")


def update_translation_job_progress(
    job_id: str,
    worker_id: str,
    progress: float,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return update_job_progress(
        job_id,
        worker_id,
        progress,
        error_details=error_details,
        job_type="translation",
    )


def ensure_translation_job_not_cancelled(job_id: str, worker_id: str) -> None:
    ensure_job_not_cancelled(job_id, worker_id, job_type="translation")


def complete_translation_job(
    job_id: str,
    worker_id: str,
    *,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return complete_job(
        job_id,
        worker_id,
        processing_time=processing_time,
        error_details=error_details,
        job_type="translation",
    )


def fail_translation_job(
    job_id: str,
    worker_id: str,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return fail_job(
        job_id,
        worker_id,
        error_details=error_details,
        job_type="translation",
    )


def retry_legacy_job(job_type: str, legacy_job_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job_for_legacy_id(db, job_type, legacy_job_id)
    finally:
        db.close()
    return retry_job(str(unified_job.id))


def heartbeat_legacy_job(job_type: str, legacy_job_id: str, worker_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job_for_legacy_id(db, job_type, legacy_job_id)
        unified_job_id = str(unified_job.id)
    finally:
        db.close()

    return heartbeat_job(unified_job_id, worker_id, job_type=job_type)


def complete_legacy_job(
    job_type: str,
    legacy_job_id: str,
    worker_id: str,
    *,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job_for_legacy_id(db, job_type, legacy_job_id)
        unified_job_id = str(unified_job.id)
    finally:
        db.close()

    return complete_job(
        unified_job_id,
        worker_id,
        processing_time=processing_time,
        error_details=error_details,
        job_type=job_type,
    )


def fail_legacy_job(
    job_type: str,
    legacy_job_id: str,
    worker_id: str,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        unified_job = _get_unified_job_for_legacy_id(db, job_type, legacy_job_id)
        unified_job_id = str(unified_job.id)
    finally:
        db.close()

    return fail_job(
        unified_job_id,
        worker_id,
        error_details=error_details,
        job_type=job_type,
    )


__all__ = [
    "JobCancellationRequestedError",
    "JobLeaseOwnershipError",
    "claim_next_job",
    "claim_next_summarization_job",
    "claim_next_transcription_job",
    "claim_next_translation_job",
    "complete_job",
    "complete_summarization_job",
    "complete_transcription_job",
    "complete_translation_job",
    "complete_legacy_job",
    "create_summarization_job_for_transcript",
    "create_transcription_job_for_video",
    "create_translation_job_for_transcript",
    "ensure_job_not_cancelled",
    "ensure_summarization_job_not_cancelled",
    "ensure_transcription_job_not_cancelled",
    "ensure_translation_job_not_cancelled",
    "fail_job",
    "fail_summarization_job",
    "fail_transcription_job",
    "fail_translation_job",
    "fail_legacy_job",
    "get_job",
    "get_job_attempts",
    "get_summarization_job",
    "get_transcription_job",
    "get_translation_job",
    "heartbeat_job",
    "heartbeat_legacy_job",
    "heartbeat_summarization_job",
    "heartbeat_transcription_job",
    "heartbeat_translation_job",
    "request_job_cancellation",
    "retry_job",
    "retry_legacy_job",
    "serialize_job",
    "update_job_progress",
    "update_summarization_job_progress",
    "update_transcription_job_progress",
    "update_translation_job_progress",
]
