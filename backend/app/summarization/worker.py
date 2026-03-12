import logging
import time
import traceback
from typing import Any, Dict, Optional

from backend.app.domain.jobs import (
    JobCancellationRequestedError,
    claim_next_summarization_job,
    complete_summarization_job,
    ensure_summarization_job_not_cancelled,
    fail_summarization_job,
    get_summarization_job,
    heartbeat_summarization_job,
    update_summarization_job_progress,
)
from backend.app.domain.records import (
    create_summary_record,
    get_transcript,
    get_video,
    update_transcript_status,
)
from backend.app.runtime.metrics import record_metric_event
from backend.app.summarization.summarizer import (
    build_summary_variants,
    generate_summary_bundle,
    normalize_content_profile,
    render_summary_markdown,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("summarization.worker")


def infer_content_profile(video: Optional[Dict[str, Any]]) -> str:
    if not video:
        return "generic"

    hints = " ".join(
        [
            str(video.get("filename", "")),
            str((video.get("video_metadata") or {}).get("title", "")),
            str((video.get("video_metadata") or {}).get("description", "")),
        ]
    ).lower()

    if any(keyword in hints for keyword in ["meeting", "standup", "sync", "call", "demo"]):
        return "meeting"
    if any(keyword in hints for keyword in ["podcast", "episode", "show"]):
        return "podcast"
    if any(keyword in hints for keyword in ["lecture", "lesson", "class", "course", "seminar"]):
        return "lecture"
    if any(keyword in hints for keyword in ["interview", "q&a", "qa"]):
        return "interview"
    return "generic"


def get_job_from_api(job_id: str) -> Dict[str, Any]:
    return get_summarization_job(job_id)


def get_transcript_from_api(transcript_id: str) -> Dict[str, Any]:
    return get_transcript(transcript_id)


def get_video_from_api(video_id: str) -> Dict[str, Any]:
    return get_video(video_id)


def create_summary_api(
    transcript_id: str,
    content: str,
    *,
    content_profile: str,
    summary_metadata: Dict[str, Any],
    variants: Dict[str, Any],
) -> Dict[str, Any]:
    return create_summary_record(
        transcript_id,
        content,
        content_profile=content_profile,
        summary_metadata=summary_metadata,
        variants=variants,
    )


def update_transcript_status_api(transcript_id: str, status: str) -> None:
    update_transcript_status(transcript_id, status)
    logger.info("Transcript %s status updated to %s", transcript_id, status)


def update_job_status_api(
    job_id: str,
    worker_id: str,
    status: str,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        if status == "completed":
            complete_summarization_job(
                job_id,
                worker_id,
                processing_time=processing_time,
                error_details=error_details,
            )
        elif status == "failed":
            fail_summarization_job(
                job_id,
                worker_id,
                error_details=error_details or {"error": "Unknown error"},
            )
        else:
            raise ValueError(f"Unsupported summarization job status transition: {status}")

        logger.info("Updated summarization job %s status to %s", job_id, status)
    except Exception as error:
        logger.error("Error updating summarization job %s: %s", job_id, error)
        logger.error("Exception traceback: %s", traceback.format_exc())


def claim_next_summarization_job_api(worker_id: str) -> Optional[Dict[str, Any]]:
    return claim_next_summarization_job(worker_id)


def heartbeat_summarization_job_api(job_id: str, worker_id: str) -> None:
    heartbeat_summarization_job(job_id, worker_id)


def update_summarization_job_progress_api(
    job_id: str,
    worker_id: str,
    progress: float,
    *,
    error_details: Optional[Dict[str, Any]] = None,
) -> None:
    update_summarization_job_progress(
        job_id,
        worker_id,
        progress,
        error_details=error_details,
    )


def ensure_summarization_job_not_cancelled_api(job_id: str, worker_id: str) -> None:
    ensure_summarization_job_not_cancelled(job_id, worker_id)


def process_summarization_job(job_id: str, worker_id: str) -> bool:
    start_time = time.time()
    transcript_id: Optional[str] = None
    metrics: Dict[str, Any] = {}

    try:
        job = get_job_from_api(job_id)
        transcript_id = job["transcript_id"]
        requested_profile = normalize_content_profile(job.get("content_profile"))
        update_summarization_job_progress_api(job_id, worker_id, 0.05)
        ensure_summarization_job_not_cancelled_api(job_id, worker_id)

        transcript = get_transcript_from_api(transcript_id)
        if not transcript:
            error_details = {"error": f"Transcript not found: {transcript_id}"}
            update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
            return False
        update_summarization_job_progress_api(job_id, worker_id, 0.2)
        ensure_summarization_job_not_cancelled_api(job_id, worker_id)

        transcript_content = transcript["content"]
        video = None
        video_id = transcript.get("video_id")
        if video_id:
            try:
                video = get_video_from_api(video_id)
            except Exception as error:
                logger.warning("Failed to fetch video %s for summary profiling: %s", video_id, error)

        effective_content_profile = (
            requested_profile
            if requested_profile != "generic" or job.get("content_profile")
            else infer_content_profile(video)
        )
        metrics["content_profile"] = effective_content_profile
        metrics["job_requested_profile"] = job.get("content_profile")
        logger.info("Generating summary for transcript: %s", transcript_id)
        summary_bundle = generate_summary_bundle(
            transcript_content,
            (video or {}).get("filename", "manual_transcript"),
            content_profile=effective_content_profile,
            transcript_segments=transcript.get("segments"),
        )
        summary_text = render_summary_markdown(summary_bundle)
        metrics["chapter_count"] = len(summary_bundle.chapters)
        metrics["highlight_count"] = len(summary_bundle.highlights)
        metrics["keyword_count"] = len(summary_bundle.keywords)
        metrics["action_item_count"] = len(summary_bundle.action_items)
        metrics["entity_count"] = len(summary_bundle.entities)
        update_summarization_job_progress_api(job_id, worker_id, 0.7)
        ensure_summarization_job_not_cancelled_api(job_id, worker_id)

        create_summary_api(
            transcript_id,
            summary_text,
            content_profile=summary_bundle.content_profile,
            summary_metadata=summary_bundle.model_dump(),
            variants=build_summary_variants(summary_bundle),
        )
        update_transcript_status_api(transcript_id, "summarized")
        update_summarization_job_progress_api(job_id, worker_id, 0.95)

        processing_time = time.time() - start_time
        metrics["total_processing_seconds"] = round(processing_time, 3)
        update_job_status_api(
            job_id,
            worker_id,
            "completed",
            processing_time=processing_time,
            error_details={"metrics": metrics},
        )
        record_metric_event(
            "summary_time_seconds",
            processing_time,
            source="summarization_worker",
            labels={"content_profile": summary_bundle.content_profile},
        )

        logger.info(
            "Summarization completed for transcript %s in %.2f seconds",
            transcript_id,
            processing_time,
        )
        return True

    except JobCancellationRequestedError:
        logger.info("Cancellation requested for summarization job %s", job_id)
        processing_time = time.time() - start_time
        complete_summarization_job(
            job_id,
            worker_id,
            processing_time=processing_time,
            error_details={"error": "Job cancelled by request", "metrics": metrics},
        )
        return False
    except Exception as error:
        logger.error("Error processing summarization job %s: %s", job_id, error)
        logger.error("Exception traceback: %s", traceback.format_exc())

        error_details = {
            "error": str(error),
            "traceback": traceback.format_exc(),
            "metrics": metrics,
        }
        update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
        return False
