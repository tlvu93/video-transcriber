import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Type

from api.config import IS_POSTGRES, JOB_LEASE_DURATION_SECONDS
from api.models import SummarizationJob, TranscriptionJob, TranslationJob
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("job_queue")


class JobLeaseOwnershipError(ValueError):
    """Raised when a worker attempts to mutate a job it does not own."""


def _lease_expiration() -> datetime:
    return datetime.utcnow() + timedelta(seconds=JOB_LEASE_DURATION_SECONDS)


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

    if IS_POSTGRES:
        return query.with_for_update(skip_locked=True).first()

    return query.first()


def _ensure_worker_owns_job(job, worker_id: str) -> None:
    if job.worker_id != worker_id or job.status != "processing":
        raise JobLeaseOwnershipError(
            f"Worker {worker_id} does not own job {job.id}. Current worker: {job.worker_id}, status: {job.status}"
        )


def get_next_transcription_job(db: Session) -> Optional[TranscriptionJob]:
    """Return the next pending transcription job without claiming it."""
    return (
        db.query(TranscriptionJob)
        .filter(TranscriptionJob.status == "pending")
        .order_by(TranscriptionJob.created_at)
        .first()
    )


def get_next_summarization_job(db: Session) -> Optional[SummarizationJob]:
    """Return the next pending summarization job without claiming it."""
    return (
        db.query(SummarizationJob)
        .filter(SummarizationJob.status == "pending")
        .order_by(SummarizationJob.created_at)
        .first()
    )


def get_next_translation_job(db: Session) -> Optional[TranslationJob]:
    """Return the next pending translation job without claiming it."""
    return db.query(TranslationJob).filter(TranslationJob.status == "pending").order_by(TranslationJob.created_at).first()


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
    db.commit()
    db.refresh(job)
    logger.info("Worker %s claimed %s job %s", worker_id, model.__tablename__, job.id)
    return job


def heartbeat_job(job, worker_id: str, db: Session):
    """Extend a worker lease for an in-flight job."""
    _ensure_worker_owns_job(job, worker_id)
    job.lease_expires_at = _lease_expiration()
    db.commit()
    db.refresh(job)
    logger.info("Worker %s refreshed lease for job %s", worker_id, job.id)
    return job


def mark_job_started(job, db: Session, worker_id: Optional[str] = None) -> None:
    """Legacy start helper retained for compatibility with older manual flows."""
    job.status = "processing"
    job.started_at = datetime.utcnow()
    if worker_id is not None:
        job.worker_id = worker_id
        job.lease_expires_at = _lease_expiration()
    db.commit()
    logger.info("Job %s marked as started", job.id)


def mark_job_completed(job, processing_time: float, db: Session, worker_id: Optional[str] = None) -> None:
    """Mark a job as completed and clear any active lease."""
    if worker_id is not None:
        _ensure_worker_owns_job(job, worker_id)

    job.status = "completed"
    job.completed_at = datetime.utcnow()
    job.processing_time_seconds = processing_time
    job.worker_id = None
    job.lease_expires_at = None
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
    db.commit()
    logger.info("Job %s marked as failed: %s", job.id, error_details)


def create_transcription_job(video_id, db: Session) -> TranscriptionJob:
    """Create a new transcription job."""
    job = TranscriptionJob(video_id=video_id, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created transcription job %s for video %s", job.id, video_id)
    return job


def create_summarization_job(transcript_id, db: Session) -> SummarizationJob:
    """Create a new summarization job."""
    job = SummarizationJob(transcript_id=transcript_id, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created summarization job %s for transcript %s", job.id, transcript_id)
    return job


def create_translation_job(transcript_id, target_language, source_language=None, db: Session = None) -> TranslationJob:
    """Create a new translation job."""
    job = TranslationJob(
        transcript_id=transcript_id,
        target_language=target_language,
        source_language=source_language,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    logger.info("Created translation job %s for transcript %s to %s", job.id, transcript_id, target_language)
    return job
