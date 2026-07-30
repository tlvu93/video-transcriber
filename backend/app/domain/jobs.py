from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlalchemy import and_, or_

from backend.app.domain.events import publish_job_live_update_sync
from backend.app.persistence.database import SessionLocal
from backend.app.persistence.models import JobAttempt, Transcript, UnifiedJob, Video
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

JOB_TYPE_SPECS: dict[str, dict[str, str]] = {
    "transcription": {
        "legacy_table": "transcription_jobs",
        "subject_type": "video",
        "subject_key": "video_id",
    },
    "summarization": {
        "legacy_table": "summarization_jobs",
        "subject_type": "transcript",
        "subject_key": "transcript_id",
    },
    "translation": {
        "legacy_table": "translation_jobs",
        "subject_type": "transcript",
        "subject_key": "transcript_id",
    },
}


class JobLeaseOwnershipError(ValueError):
    """Raised when a worker attempts to mutate a job it does not own."""


class JobCancellationRequestedError(RuntimeError):
    """Raised when a worker should stop because cancellation was requested."""


def _lease_expiration() -> datetime:
    return _utcnow() + timedelta(seconds=JOB_LEASE_DURATION_SECONDS)


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_job_spec(job_type: str) -> dict[str, str]:
    if job_type not in JOB_TYPE_SPECS:
        raise ValueError(f"Unsupported job type: {job_type}")
    return JOB_TYPE_SPECS[job_type]


def _build_payload(
    job_type: str,
    subject_id: str,
    *,
    source_language: Optional[str] = None,
    target_language: Optional[str] = None,
    content_profile: Optional[str] = None,
    style_guide: Optional[str] = None,
    glossary_terms: Optional[list[dict[str, str]]] = None,
) -> Dict[str, Any]:
    spec = _get_job_spec(job_type)
    payload: Dict[str, Any] = {
        spec["subject_key"]: str(subject_id),
    }

    if job_type == "summarization":
        if content_profile:
            payload["content_profile"] = content_profile
        return payload

    if job_type == "translation":
        if source_language:
            payload["source_language"] = source_language
        if target_language:
            payload["target_language"] = target_language
        payload["style_guide"] = style_guide
        payload["glossary_terms"] = glossary_terms or []

    return payload


def _create_unified_job(
    db,
    *,
    job_type: str,
    subject_id: str,
    payload: Dict[str, Any],
) -> UnifiedJob:
    spec = _get_job_spec(job_type)
    compatibility_id = str(uuid4())
    unified_job = UnifiedJob(
        id=compatibility_id,
        legacy_job_table=spec["legacy_table"],
        legacy_job_id=compatibility_id,
        job_type=job_type,
        subject_type=spec["subject_type"],
        subject_id=str(subject_id),
        status=JOB_STATUS_PENDING,
        priority=100,
        payload=payload,
        progress=0.0,
        attempt_count=0,
    )
    db.add(unified_job)
    db.flush()
    return unified_job


def _get_unified_job(db, job_id: str, *, job_type: Optional[str] = None) -> UnifiedJob:
    query = db.query(UnifiedJob).filter(UnifiedJob.id == job_id)
    if job_type:
        query = query.filter(UnifiedJob.job_type == job_type)

    unified_job = query.first()
    if not unified_job:
        raise ValueError(f"Unified job not found: {job_id}")
    return unified_job


def _get_unified_job_for_legacy_id(db, job_type: str, legacy_job_id: str) -> UnifiedJob:
    unified_job = (
        db.query(UnifiedJob)
        .filter(UnifiedJob.job_type == job_type)
        .filter(UnifiedJob.legacy_job_id == legacy_job_id)
        .first()
    )
    if not unified_job:
        raise ValueError(f"Unified {job_type} job not found for legacy id: {legacy_job_id}")
    return unified_job


def _close_active_attempts(
    unified_job: UnifiedJob,
    db,
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


def _start_attempt(unified_job: UnifiedJob, worker_id: str, db, *, now: datetime) -> None:
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


def _get_active_attempt(unified_job: UnifiedJob, db) -> Optional[JobAttempt]:
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


def _finalize_expired_cancellations(job_type: str, db, *, now: datetime) -> None:
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
        unified_job.status = JOB_STATUS_CANCELLED
        unified_job.completed_at = now
        unified_job.worker_id = None
        unified_job.lease_expires_at = None
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


def _claimable_job_query(job_type: str, db, *, now: datetime):
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
        now = _utcnow()
        _finalize_expired_cancellations(job_type, db, now=now)
        unified_job = _claimable_job_query(job_type, db, now=now).with_for_update(skip_locked=True).first()
        if not unified_job:
            db.commit()
            return None

        unified_job.status = JOB_STATUS_PROCESSING
        unified_job.worker_id = worker_id
        unified_job.started_at = now
        unified_job.completed_at = None
        unified_job.lease_expires_at = _lease_expiration()
        unified_job.progress = 0.0
        unified_job.error_details = None
        _start_attempt(unified_job, worker_id, db, now=now)
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
            raise JobCancellationRequestedError(f"Cancellation requested for job {job_id}")
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

        now = _utcnow()
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
        now = _utcnow()
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
        now = _utcnow()
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
            raise ValueError(f"Job {job_id} cannot be cancelled from status {unified_job.status}")

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
            raise ValueError(f"Job {job_id} is not retryable from status {unified_job.status}")

        unified_job.status = JOB_STATUS_PENDING
        unified_job.worker_id = None
        unified_job.lease_expires_at = None
        unified_job.started_at = None
        unified_job.completed_at = None
        unified_job.processing_time_seconds = None
        unified_job.error_details = None
        unified_job.progress = 0.0

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


def create_transcription_job_for_video(video_id: str) -> Dict[str, Any]:
    db = SessionLocal()
    try:
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video not found: {video_id}")

        unified_job = _create_unified_job(
            db,
            job_type="transcription",
            subject_id=video_id,
            payload=_build_payload("transcription", video_id),
        )
        db.commit()
        db.refresh(unified_job)
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

        unified_job = _create_unified_job(
            db,
            job_type="summarization",
            subject_id=transcript_id,
            payload=_build_payload(
                "summarization",
                transcript_id,
                content_profile=content_profile,
            ),
        )
        db.commit()
        db.refresh(unified_job)
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

        unified_job = _create_unified_job(
            db,
            job_type="translation",
            subject_id=transcript_id,
            payload=_build_payload(
                "translation",
                transcript_id,
                source_language=source_language,
                target_language=target_language,
                style_guide=style_guide,
                glossary_terms=glossary_terms,
            ),
        )
        db.commit()
        db.refresh(unified_job)
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
