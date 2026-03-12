import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Type

from backend.app.persistence.models import JobAttempt, SummarizationJob, TranscriptionJob, TranslationJob, UnifiedJob
from backend.app.runtime.config import JOB_LEASE_DURATION_SECONDS
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("backend.domain.job_queue")


JOB_SPEC_BY_TABLE = {
    "transcription_jobs": {
        "job_type": "transcription",
        "subject_type": "video",
        "subject_attr": "video_id",
    },
    "summarization_jobs": {
        "job_type": "summarization",
        "subject_type": "transcript",
        "subject_attr": "transcript_id",
    },
    "translation_jobs": {
        "job_type": "translation",
        "subject_type": "transcript",
        "subject_attr": "transcript_id",
    },
}


class JobLeaseOwnershipError(ValueError):
    """Raised when a worker attempts to mutate a job it does not own."""


def _lease_expiration() -> datetime:
    return datetime.utcnow() + timedelta(seconds=JOB_LEASE_DURATION_SECONDS)


def _get_job_spec(job_or_model: Any) -> Dict[str, str]:
    table_name = getattr(job_or_model, "__tablename__", None)
    if table_name is None and hasattr(job_or_model, "__table__"):
        table_name = job_or_model.__table__.name

    if table_name not in JOB_SPEC_BY_TABLE:
        raise ValueError(f"Unsupported job table for unified orchestration: {table_name}")

    return {
        "table_name": table_name,
        **JOB_SPEC_BY_TABLE[table_name],
    }


def _build_unified_payload(job: Any) -> Dict[str, Any]:
    if isinstance(job, SummarizationJob):
        payload = {}
        if job.content_profile:
            payload["content_profile"] = job.content_profile
        return payload
    if isinstance(job, TranslationJob):
        payload = {
            "source_language": job.source_language,
            "target_language": job.target_language,
        }
        if job.style_guide:
            payload["style_guide"] = job.style_guide
        if job.glossary_terms:
            payload["glossary_terms"] = job.glossary_terms
        return payload
    return {}


def _get_unified_job(job: Any, db: Session) -> Optional[UnifiedJob]:
    spec = _get_job_spec(job)
    return (
        db.query(UnifiedJob)
        .filter(
            UnifiedJob.legacy_job_table == spec["table_name"],
            UnifiedJob.legacy_job_id == str(job.id),
        )
        .first()
    )


def _ensure_unified_job(job: Any, db: Session) -> UnifiedJob:
    spec = _get_job_spec(job)
    unified_job = _get_unified_job(job, db)
    if unified_job:
        return unified_job

    unified_job = UnifiedJob(
        legacy_job_table=spec["table_name"],
        legacy_job_id=str(job.id),
        job_type=spec["job_type"],
        subject_type=spec["subject_type"],
        subject_id=str(getattr(job, spec["subject_attr"])),
        status=job.status,
        payload=_build_unified_payload(job),
        worker_id=job.worker_id,
        lease_expires_at=job.lease_expires_at,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        processing_time_seconds=job.processing_time_seconds,
        error_details=job.error_details,
        attempt_count=0,
    )
    db.add(unified_job)
    db.flush()
    return unified_job


def _close_active_attempts(unified_job: UnifiedJob, db: Session, *, now: datetime) -> None:
    active_attempts = (
        db.query(JobAttempt)
        .filter(
            JobAttempt.job_id == unified_job.id,
            JobAttempt.completed_at.is_(None),
        )
        .all()
    )
    for attempt in active_attempts:
        attempt.status = "expired"
        attempt.completed_at = now
        attempt.error_details = {
            "error": "Lease expired before completion",
        }


def _start_unified_attempt(unified_job: UnifiedJob, worker_id: str, db: Session, *, now: datetime) -> None:
    _close_active_attempts(unified_job, db, now=now)
    next_attempt_number = int(unified_job.attempt_count or 0) + 1
    unified_job.attempt_count = next_attempt_number
    db.add(
        JobAttempt(
            job_id=unified_job.id,
            attempt_number=next_attempt_number,
            worker_id=worker_id,
            status="processing",
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


def _sync_unified_job_from_legacy(job: Any, db: Session) -> UnifiedJob:
    unified_job = _ensure_unified_job(job, db)
    unified_job.status = job.status
    unified_job.payload = _build_unified_payload(job)
    unified_job.worker_id = job.worker_id
    unified_job.lease_expires_at = job.lease_expires_at
    unified_job.created_at = job.created_at
    unified_job.started_at = job.started_at
    unified_job.completed_at = job.completed_at
    unified_job.processing_time_seconds = job.processing_time_seconds
    unified_job.error_details = job.error_details
    return unified_job


def _get_claimable_job(model: Type, db: Session):
    now = datetime.utcnow()
    query = (
        db.query(model)
        .filter(
            or_(
                model.status == "pending",
                and_(
                    model.status == "processing",
                    model.lease_expires_at.isnot(None),
                    model.lease_expires_at < now,
                ),
            )
        )
        .order_by(model.created_at)
    )

    return query.with_for_update(skip_locked=True).first()


def _ensure_worker_owns_job(job, worker_id: str) -> None:
    if job.worker_id != worker_id or job.status != "processing":
        raise JobLeaseOwnershipError(
            f"Worker {worker_id} does not own job {job.id}. Current worker: {job.worker_id}, status: {job.status}"
        )


def claim_job(model: Type, db: Session, worker_id: str):
    """Atomically claim the next available job for a worker."""
    job = _get_claimable_job(model, db)
    if not job:
        return None

    now = datetime.utcnow()
    job.status = "processing"
    job.worker_id = worker_id
    job.started_at = now
    job.completed_at = None
    job.lease_expires_at = _lease_expiration()
    unified_job = _sync_unified_job_from_legacy(job, db)
    _start_unified_attempt(unified_job, worker_id, db, now=now)
    db.commit()
    db.refresh(job)
    logger.info("Worker %s claimed %s job %s", worker_id, model.__tablename__, job.id)
    return job


def heartbeat_job(job, worker_id: str, db: Session):
    """Extend a worker lease for an in-flight job."""
    _ensure_worker_owns_job(job, worker_id)
    job.lease_expires_at = _lease_expiration()
    _sync_unified_job_from_legacy(job, db)
    db.commit()
    db.refresh(job)
    logger.info("Worker %s refreshed lease for job %s", worker_id, job.id)
    return job


def mark_job_completed(job, processing_time: float, db: Session, worker_id: Optional[str] = None) -> None:
    """Mark a job as completed and clear any active lease."""
    if worker_id is not None:
        _ensure_worker_owns_job(job, worker_id)

    job.status = "completed"
    job.completed_at = datetime.utcnow()
    job.processing_time_seconds = processing_time
    job.worker_id = None
    job.lease_expires_at = None
    unified_job = _sync_unified_job_from_legacy(job, db)
    active_attempt = _get_active_attempt(unified_job, db)
    if active_attempt:
        active_attempt.status = "completed"
        active_attempt.completed_at = job.completed_at
        active_attempt.processing_time_seconds = processing_time
    db.commit()
    logger.info("Job %s marked as completed in %.2f seconds", job.id, processing_time)


def mark_job_failed(job, error_details: Dict[str, Any], db: Session, worker_id: Optional[str] = None) -> None:
    """Mark a job as failed and clear any active lease."""
    if worker_id is not None:
        _ensure_worker_owns_job(job, worker_id)

    job.status = "failed"
    job.completed_at = datetime.utcnow()
    job.error_details = error_details
    job.worker_id = None
    job.lease_expires_at = None
    unified_job = _sync_unified_job_from_legacy(job, db)
    active_attempt = _get_active_attempt(unified_job, db)
    if active_attempt:
        active_attempt.status = "failed"
        active_attempt.completed_at = job.completed_at
        active_attempt.error_details = error_details
    db.commit()
    logger.info("Job %s marked as failed: %s", job.id, error_details)


def create_transcription_job(video_id, db: Session) -> TranscriptionJob:
    """Create a new transcription job."""
    job = TranscriptionJob(video_id=video_id, status="pending")
    db.add(job)
    db.flush()
    _sync_unified_job_from_legacy(job, db)
    db.commit()
    db.refresh(job)
    logger.info("Created transcription job %s for video %s", job.id, video_id)
    return job


def create_summarization_job(
    transcript_id,
    db: Session,
    *,
    content_profile: Optional[str] = None,
) -> SummarizationJob:
    """Create a new summarization job."""
    job = SummarizationJob(
        transcript_id=transcript_id,
        content_profile=content_profile,
        status="pending",
    )
    db.add(job)
    db.flush()
    _sync_unified_job_from_legacy(job, db)
    db.commit()
    db.refresh(job)
    logger.info("Created summarization job %s for transcript %s", job.id, transcript_id)
    return job


def create_translation_job(
    transcript_id,
    target_language,
    source_language=None,
    *,
    style_guide=None,
    glossary_terms=None,
    db: Session = None,
) -> TranslationJob:
    """Create a new translation job."""
    job = TranslationJob(
        transcript_id=transcript_id,
        target_language=target_language,
        source_language=source_language,
        style_guide=style_guide,
        glossary_terms=glossary_terms,
        status="pending",
    )
    db.add(job)
    db.flush()
    _sync_unified_job_from_legacy(job, db)
    db.commit()
    db.refresh(job)
    logger.info("Created translation job %s for transcript %s to %s", job.id, transcript_id, target_language)
    return job
