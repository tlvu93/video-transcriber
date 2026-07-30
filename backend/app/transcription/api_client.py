import logging
import os
from typing import Any

from backend.app.domain.jobs import (
    claim_next_transcription_job,
    complete_transcription_job,
    ensure_transcription_job_not_cancelled,
    fail_transcription_job,
    get_transcription_job,
    heartbeat_transcription_job,
    update_transcription_job_progress,
)
from backend.app.domain.records import (
    create_transcript_record,
    get_video,
    update_video_status,
)
from backend.app.transcription.config import VIDEO_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("transcription.api_client")

os.makedirs(VIDEO_DIR, exist_ok=True)
logger.info("Video directory: %s", VIDEO_DIR)


def get_job_from_api(job_id: str) -> dict[str, Any]:
    return get_transcription_job(job_id)


def claim_next_transcription_job_api(worker_id: str) -> dict[str, Any] | None:
    return claim_next_transcription_job(worker_id)


def heartbeat_transcription_job_api(job_id: str, worker_id: str) -> dict[str, Any] | None:
    return heartbeat_transcription_job(job_id, worker_id)


def update_transcription_job_progress_api(
    job_id: str,
    worker_id: str,
    progress: float,
    *,
    error_details: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        return update_transcription_job_progress(
            job_id,
            worker_id,
            progress,
            error_details=error_details,
        )
    except Exception as error:
        logger.error("Error updating transcription job progress: %s", error)
        return None


def ensure_transcription_job_not_cancelled_api(job_id: str, worker_id: str) -> None:
    ensure_transcription_job_not_cancelled(job_id, worker_id)


def get_video_from_api(video_id: str) -> dict[str, Any]:
    return get_video(video_id)


def update_video_status_api(video_id: str, status: str) -> None:
    update_video_status(video_id, status)
    logger.info("Video %s status updated to %s", video_id, status)


def create_transcript_api(
    video_id: str,
    content: str,
    segments: list[dict[str, Any]] | None = None,
    language_code: str | None = None,
) -> dict[str, Any] | None:
    try:
        transcript = create_transcript_record(
            video_id,
            content,
            segments=segments,
            language_code=language_code,
            enqueue_summarization=True,
        )
        logger.info("Created transcript %s for video %s", transcript["id"], video_id)
        return transcript
    except Exception as error:
        logger.error("Error creating transcript: %s", error)
        return None


def complete_transcription_job_api(
    job_id: str,
    worker_id: str,
    processing_time: float | None = None,
    error_details: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        job = complete_transcription_job(
            job_id,
            worker_id,
            processing_time=processing_time,
            error_details=error_details,
        )
        logger.info("Updated transcription job %s status to completed", job_id)
        return job
    except Exception as error:
        logger.error("Error updating job status: %s", error)
        return None


def fail_transcription_job_api(
    job_id: str,
    worker_id: str,
    error_details: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    try:
        job = fail_transcription_job(
            job_id,
            worker_id,
            error_details=error_details or {"error": "Unknown error"},
        )
        logger.info("Updated transcription job %s status to failed", job_id)
        return job
    except Exception as error:
        logger.error("Error updating job status: %s", error)
        return None
