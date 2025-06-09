import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from translation.config import API_URL
from translation.translator import detect_language, translate_segments, translate_text

from common.messaging import RabbitMQClient, publish_job_status_changed_event

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translation.worker")

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()


def get_job_from_api(job_id: str) -> Dict[str, Any]:
    """Get job details from API."""
    response = requests.get(f"{API_URL}/translation-jobs/{job_id}")
    response.raise_for_status()
    return response.json()


def get_transcript_from_api(transcript_id: str) -> Dict[str, Any]:
    """Get transcript details from API."""
    response = requests.get(f"{API_URL}/transcripts/{transcript_id}")
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
    response = requests.post(f"{API_URL}/translated-transcripts/", json=data)
    response.raise_for_status()
    translation = response.json()

    # Publish translation created event
    try:
        rabbitmq_client.connect()
        # TODO: Add event publishing when implemented in common
        # publish_translation_created_event(rabbitmq_client, str(translation["id"]), str(transcript_id))
        logger.info(f"Translation created for transcript {transcript_id} in language {language}")
    except Exception as e:
        logger.error(f"Error publishing event: {str(e)}")

    return translation


def update_job_status_api(
    job_id: str,
    status: str,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> None:
    """Update the status of a translation job via the API."""
    try:
        if status == "completed":
            url = f"{API_URL}/translation-jobs/{job_id}/complete"
            data = {"status": status, "processing_time_seconds": processing_time}
        elif status == "failed":
            url = f"{API_URL}/translation-jobs/{job_id}/fail"
            data = {
                "status": status,
                "error_details": error_details or {"error": "Unknown error"},
            }
        else:
            url = f"{API_URL}/translation-jobs/{job_id}/start"
            data = {}

        response = requests.post(url, json=data)
        response.raise_for_status()

        response.json()
        logger.info(f"Updated translation job {job_id} status to {status}")

        # Publish job status changed event
        try:
            rabbitmq_client.connect()
            publish_job_status_changed_event(rabbitmq_client, "translation", str(job_id), status)
            logger.info(f"Published job.status.changed event for job {job_id}")
        except Exception as e:
            logger.error(f"Error publishing event: {str(e)}")

    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def process_translation_job(job_id: str) -> bool:
    """
    Process a translation job.

    Args:
        job_id: The ID of the translation job to process

    Returns:
        True if the job was processed successfully, False otherwise
    """
    start_time = time.time()

    try:
        # Get job details from API
        job = get_job_from_api(job_id)
        transcript_id = job["transcript_id"]
        target_language = job["target_language"]

        # Mark job as started
        update_job_status_api(job_id, "processing")

        # Get the transcript from API
        transcript = get_transcript_from_api(transcript_id)
        if not transcript:
            error_details = {"error": f"Transcript not found: {transcript_id}"}
            update_job_status_api(job_id, "failed", error_details=error_details)
            return False

        # Get the transcript content and segments
        transcript_content = transcript["content"]
        transcript_segments = transcript.get("segments", [])

        # Detect source language if not specified
        source_language = job.get("source_language")
        if not source_language:
            source_language = detect_language(transcript_content)
            logger.info(f"Detected source language: {source_language}")

        # Generate translation
        logger.info(f"Translating transcript {transcript_id} from {source_language} to {target_language}")

        # Translate the full content
        translated_content = translate_text(transcript_content, source_language, target_language)

        # Translate segments if they exist
        translated_segments = None
        if transcript_segments:
            translated_segments = translate_segments(transcript_segments, source_language, target_language)

        # Create translation record via API
        create_translation_api(transcript_id, target_language, translated_content, translated_segments)

        # Mark job as completed
        processing_time = time.time() - start_time
        update_job_status_api(job_id, "completed", processing_time=processing_time)

        logger.info(f"Translation completed for transcript {transcript_id} in {processing_time:.2f} seconds")
        return True

    except Exception as e:
        logger.error(f"Error processing translation job {job_id}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")

        # Mark job as failed
        error_details = {"error": str(e), "traceback": traceback.format_exc()}
        update_job_status_api(job_id, "failed", error_details=error_details)
        return False


def get_next_translation_job_api() -> Optional[Dict[str, Any]]:
    """Get the next pending translation job from the API."""
    try:
        response = requests.get(f"{API_URL}/translation-jobs/next")
        if response.status_code == 404:
            # No pending jobs
            return None
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error getting next translation job: {str(e)}")
        return None
