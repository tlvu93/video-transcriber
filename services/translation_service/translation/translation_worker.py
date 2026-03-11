import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from translation.config import API_URL
from translation.cache import (
    compute_translation_cache_key,
    read_cached_translation,
    write_cached_translation,
)
from translation.translator import detect_language, translate_segments, translate_text

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translation.worker")


def build_translated_content_from_segments(
    translated_segments: Optional[list], fallback_content: str
) -> str:
    """Build a plain-text transcript body from translated segments."""
    if not translated_segments:
        return fallback_content

    segment_texts = [
        str(segment.get("text", "")).strip()
        for segment in translated_segments
        if str(segment.get("text", "")).strip()
    ]

    if not segment_texts:
        return fallback_content

    return " ".join(segment_texts)


def get_job_from_api(job_id: str) -> Dict[str, Any]:
    """Get job details from API."""
    response = requests.get(f"{API_URL}/translation-jobs/{job_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def get_transcript_from_api(transcript_id: str) -> Dict[str, Any]:
    """Get transcript details from API."""
    response = requests.get(f"{API_URL}/transcripts/{transcript_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def create_translation_api(
    transcript_id: str, language: str, content: str, segments: Optional[list] = None
) -> Dict[str, Any]:
    """Create translation via API."""
    data = {
        "transcript_id": transcript_id,
        "language": language,
        "content": content,
        "segments": segments,
        "status": "completed",
    }
    response = requests.post(f"{API_URL}/translated-transcripts/", json=data, timeout=30)
    response.raise_for_status()
    translation = response.json()
    logger.info(f"Translation created for transcript {transcript_id} in language {language}")
    return translation


def update_job_status_api(
    job_id: str,
    worker_id: str,
    status: str,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> None:
    """Update the status of a translation job via the API."""
    try:
        if status == "completed":
            url = f"{API_URL}/translation-jobs/{job_id}/complete"
            data = {
                "status": status,
                "worker_id": worker_id,
                "processing_time_seconds": processing_time,
            }
            if error_details is not None:
                data["error_details"] = error_details
        elif status == "failed":
            url = f"{API_URL}/translation-jobs/{job_id}/fail"
            data = {
                "status": status,
                "worker_id": worker_id,
                "error_details": error_details or {"error": "Unknown error"},
            }
        else:
            raise ValueError(f"Unsupported translation job status transition: {status}")

        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()

        logger.info(f"Updated translation job {job_id} status to {status}")

    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def claim_next_translation_job_api(worker_id: str) -> Optional[Dict[str, Any]]:
    """Claim the next available translation job."""
    response = requests.post(
        f"{API_URL}/translation-jobs/claim",
        json={"worker_id": worker_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def heartbeat_translation_job_api(job_id: str, worker_id: str) -> None:
    """Refresh a translation job lease."""
    response = requests.post(
        f"{API_URL}/translation-jobs/{job_id}/heartbeat",
        json={"worker_id": worker_id},
        timeout=30,
    )
    response.raise_for_status()


def process_translation_job(job_id: str, worker_id: str) -> bool:
    """
    Process a translation job.

    Args:
        job_id: The ID of the translation job to process

    Returns:
        True if the job was processed successfully, False otherwise
    """
    start_time = time.time()
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        timings: Dict[str, Any] = {}
        try:
            # Get job details from API
            job_fetch_started_at = time.perf_counter()
            job = get_job_from_api(job_id)
            transcript_id = job["transcript_id"]
            target_language = job["target_language"]
            timings["job_fetch_seconds"] = round(
                time.perf_counter() - job_fetch_started_at,
                3,
            )
            timings["target_language"] = target_language

            # Get the transcript from API
            transcript_fetch_started_at = time.perf_counter()
            transcript = get_transcript_from_api(transcript_id)
            if not transcript:
                error_details = {"error": f"Transcript not found: {transcript_id}"}
                update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
                return False
            timings["transcript_fetch_seconds"] = round(
                time.perf_counter() - transcript_fetch_started_at,
                3,
            )

            # Get the transcript content and segments
            transcript_content = transcript["content"]
            transcript_segments = transcript.get("segments", [])
            timings["input_characters"] = len(transcript_content or "")
            timings["segment_count"] = len(transcript_segments or [])

            # Use language from transcript if available, otherwise detect
            source_language = transcript.get("language_code") or job.get("source_language")
            if not source_language:
                logger.info("No source language specified, attempting to detect...")
                language_detect_started_at = time.perf_counter()
                source_language = detect_language(transcript_content)
                timings["language_detection_seconds"] = round(
                    time.perf_counter() - language_detect_started_at,
                    3,
                )
                logger.info(f"Detected source language: {source_language}")
            else:
                timings["language_detection_seconds"] = 0.0
                logger.info(f"Using source language from transcript: {source_language}")
            timings["source_language"] = source_language

            cache_lookup_started_at = time.perf_counter()
            cache_key = compute_translation_cache_key(
                transcript_content,
                transcript_segments,
                source_language,
                target_language,
            )
            cached_translation = read_cached_translation(cache_key)
            timings["cache_key_prefix"] = cache_key[:12]
            timings["cache_lookup_seconds"] = round(
                time.perf_counter() - cache_lookup_started_at,
                3,
            )
            timings["cache_hit"] = cached_translation is not None

            # Check if translation is actually needed
            if cached_translation:
                logger.info(
                    "Reusing cached translation for transcript %s from %s to %s",
                    transcript_id,
                    source_language,
                    target_language,
                )
                translated_content = cached_translation.get("content", transcript_content)
                translated_segments = cached_translation.get("segments")
                timings["translation_strategy"] = "cache_hit"
                timings["translation_seconds"] = 0.0
            else:
                translation_started_at = time.perf_counter()
                if source_language == target_language:
                    logger.info(f"Source and target languages are the same ({source_language}), creating copy")
                    translated_content = transcript_content
                    translated_segments = transcript_segments
                    timings["translation_strategy"] = "copy"
                else:
                    logger.info(f"Translating transcript {transcript_id} from {source_language} to {target_language}")
                    if transcript_segments:
                        translated_segments = translate_segments(
                            transcript_segments,
                            source_language,
                            target_language,
                        )
                        translated_content = build_translated_content_from_segments(
                            translated_segments,
                            transcript_content,
                        )
                        timings["translation_strategy"] = "segment_batches"
                    else:
                        translated_content = translate_text(
                            transcript_content,
                            source_language,
                            target_language,
                        )
                        translated_segments = None
                        timings["translation_strategy"] = "full_content"

                    if translated_content == transcript_content and source_language != target_language:
                        logger.warning(
                            "Translation returned original text, this might indicate a translation failure"
                        )
                timings["translation_seconds"] = round(
                    time.perf_counter() - translation_started_at,
                    3,
                )

                cache_write_started_at = time.perf_counter()
                write_cached_translation(
                    cache_key,
                    content=translated_content,
                    segments=translated_segments,
                    source_language=source_language,
                    target_language=target_language,
                    strategy=timings["translation_strategy"],
                )
                timings["cache_write_seconds"] = round(
                    time.perf_counter() - cache_write_started_at,
                    3,
                )
            timings["output_characters"] = len(translated_content or "")

            # Create translation record via API
            persist_started_at = time.perf_counter()
            create_translation_api(transcript_id, target_language, translated_content, translated_segments)
            timings["persist_seconds"] = round(
                time.perf_counter() - persist_started_at,
                3,
            )

            # Mark job as completed
            processing_time = time.time() - start_time
            timings["total_processing_seconds"] = round(processing_time, 3)
            update_job_status_api(
                job_id,
                worker_id,
                "completed",
                processing_time=processing_time,
                error_details={"metrics": timings},
            )

            logger.info(
                "Translation completed for transcript %s in %.2f seconds with metrics: %s",
                transcript_id,
                processing_time,
                timings,
            )
            return True

        except Exception as e:
            retry_count += 1
            logger.error(f"Error processing translation job {job_id} (attempt {retry_count}/{max_retries}): {str(e)}")
            
            if retry_count < max_retries:
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            else:
                logger.error(f"All retry attempts failed for job {job_id}")
                logger.error(f"Exception traceback: {traceback.format_exc()}")

                # Mark job as failed
                error_details = {
                    "error": str(e),
                    "traceback": traceback.format_exc()[:1000],
                    "retry_count": retry_count,
                    "metrics": timings,
                }
                update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
                return False

    return False
