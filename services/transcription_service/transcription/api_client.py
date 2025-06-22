import logging
import os
import traceback
from typing import Any, Dict, List, Optional

import requests
from transcription.config import API_URL, VIDEO_DIR

from common.messaging import RabbitMQClient, publish_job_status_changed_event, publish_transcription_created_event

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("api_client")

# Create video directory
os.makedirs(VIDEO_DIR, exist_ok=True)
logger.info(f"Video directory: {VIDEO_DIR}")

#######################
# Core API Functions  #
#######################


def api_request(method: str, url: str, **kwargs) -> Dict[str, Any]:
    """Make an API request with error handling."""
    try:
        if "timeout" not in kwargs:
            kwargs["timeout"] = 30

        response = getattr(requests, method.lower())(url, **kwargs)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request error ({method} {url}): {str(e)}")
        raise


#######################
# Data Retrieval      #
#######################


def get_job_from_api(job_id: str) -> Dict[str, Any]:
    """Get job details from API."""
    return api_request("get", f"{API_URL}/transcription-jobs/{job_id}")


def get_next_transcription_job_api() -> Optional[Dict[str, Any]]:
    """
    Get the next pending transcription job from the API.

    Returns:
        The next pending transcription job, or None if no jobs are pending
    """
    try:
        return api_request("get", f"{API_URL}/transcription-jobs/next")
    except Exception as e:
        if "404" in str(e):
            # No pending jobs
            return None
        logger.error(f"Error getting next transcription job: {str(e)}")
        raise


def get_all_pending_transcription_jobs_api() -> List[Dict[str, Any]]:
    """
    Get all pending transcription jobs from the API.

    Returns:
        List of all pending transcription jobs, or empty list if no jobs are pending
    """
    try:
        result = api_request("get", f"{API_URL}/transcription-jobs?status=pending")
        if isinstance(result, list):
            return result
        return []
    except Exception as e:
        if "404" in str(e):
            # No pending jobs
            return []
        logger.error(f"Error getting pending transcription jobs: {str(e)}")
        raise


def get_video_from_api(video_id: str) -> Dict[str, Any]:
    """Get video details from API."""
    return api_request("get", f"{API_URL}/videos/{video_id}")


def update_video_status_api(video_id: str, status: str) -> None:
    """Update video status via API."""
    api_request("patch", f"{API_URL}/videos/{video_id}", json={"status": status})
    logger.info(f"Video {video_id} status updated to {status}")


#######################
# Data Creation/Updates #
#######################


def create_transcript_api(
    video_id: str, content: str, segments: Optional[List[Dict[str, Any]]] = None, language_code: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Create a transcript via the API."""
    try:
        url = f"{API_URL}/transcripts/"
        data = {
            "video_id": video_id,
            "source_type": "video",
            "content": content,
            "format": "txt",
            "status": "completed",
            "language_code": language_code,
            "segments": segments or [],
        }

        response = api_request("post", url, json=data)
        transcript = response
        logger.info(f"Created transcript {transcript['id']} for video {video_id}")

        # Create a summarization job for the transcript via API
        job_url = f"{API_URL}/summarization-jobs/"
        job_data = {"transcript_id": transcript["id"]}

        job_response = api_request("post", job_url, json=job_data)
        job = job_response
        logger.info(f"Created summarization job {job['id']} for transcript {transcript['id']} via API")

        # Publish transcript created event with connection management
        try:
            rabbitmq_client = RabbitMQClient()
            rabbitmq_client.connect()
            publish_transcription_created_event(rabbitmq_client, str(transcript["id"]), str(video_id))
            rabbitmq_client.close()
            logger.info(f"Published transcription.created event for transcript {transcript['id']}")
        except Exception as e:
            logger.error(f"Error publishing event: {str(e)}")
            logger.info("Continuing with processing as summarization job was already created via API")

        return transcript

    except Exception as e:
        logger.error(f"Error creating transcript: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None


def update_job_status_api(
    job_id: str, status: str, processing_time: Optional[float] = None, error_details: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Update the status of a transcription job via the API."""
    try:
        if status == "completed":
            url = f"{API_URL}/transcription-jobs/{job_id}/complete"
            data = {"status": status, "processing_time_seconds": processing_time}
        elif status == "failed":
            url = f"{API_URL}/transcription-jobs/{job_id}/fail"
            data = {
                "status": status,
                "error_details": error_details or {"error": "Unknown error"},
            }
        else:
            url = f"{API_URL}/transcription-jobs/{job_id}/start"
            data = {}

        job = api_request("post", url, json=data)
        logger.info(f"Updated transcription job {job_id} status to {status}")

        # Publish job status changed event with connection management
        try:
            rabbitmq_client = RabbitMQClient()
            rabbitmq_client.connect()
            publish_job_status_changed_event(rabbitmq_client, "transcription", str(job_id), status)
            rabbitmq_client.close()
            logger.info(f"Published job.status.changed event for job {job_id}")
        except Exception as e:
            logger.error(f"Error publishing event: {str(e)}")

        return job

    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        return None
