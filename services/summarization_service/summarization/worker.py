import logging
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from summarization.config import API_URL
from summarization.summarizer import create_summary

# Add the project root directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("summarization.worker")


def get_job_from_api(job_id: str) -> Dict[str, Any]:
    """Get job details from API."""
    response = requests.get(f"{API_URL}/summarization-jobs/{job_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def get_transcript_from_api(transcript_id: str) -> Dict[str, Any]:
    """Get transcript details from API."""
    response = requests.get(f"{API_URL}/transcripts/{transcript_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def get_video_from_api(video_id: str) -> Dict[str, Any]:
    """Get video details from API."""
    response = requests.get(f"{API_URL}/videos/{video_id}", timeout=30)
    response.raise_for_status()
    return response.json()


def create_summary_api(transcript_id: str, content: str) -> Dict[str, Any]:
    """Create summary via API."""
    data = {"transcript_id": transcript_id, "content": content, "status": "completed"}
    response = requests.post(f"{API_URL}/summaries/", json=data, timeout=30)
    response.raise_for_status()
    return response.json()


def update_transcript_status_api(transcript_id: str, status: str) -> None:
    """Update transcript status via API."""
    data = {"status": status}
    response = requests.patch(f"{API_URL}/transcripts/{transcript_id}", json=data, timeout=30)
    response.raise_for_status()
    logger.info(f"Transcript {transcript_id} status updated to {status}")


def update_job_status_api(
    job_id: str,
    worker_id: str,
    status: str,
    processing_time: Optional[float] = None,
    error_details: Optional[Dict[str, Any]] = None,
) -> None:
    """Update the terminal status of a leased summarization job via the API."""
    try:
        if status == "completed":
            url = f"{API_URL}/summarization-jobs/{job_id}/complete"
            data = {
                "status": status,
                "worker_id": worker_id,
                "processing_time_seconds": processing_time,
            }
        elif status == "failed":
            url = f"{API_URL}/summarization-jobs/{job_id}/fail"
            data = {
                "status": status,
                "worker_id": worker_id,
                "error_details": error_details or {"error": "Unknown error"},
            }
        else:
            raise ValueError(f"Unsupported summarization job status transition: {status}")

        response = requests.post(url, json=data, timeout=30)
        response.raise_for_status()

        logger.info(f"Updated summarization job {job_id} status to {status}")

    except Exception as e:
        logger.error(f"Error updating job status: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def claim_next_summarization_job_api(worker_id: str) -> Optional[Dict[str, Any]]:
    """Claim the next available summarization job."""
    response = requests.post(
        f"{API_URL}/summarization-jobs/claim",
        json={"worker_id": worker_id},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def heartbeat_summarization_job_api(job_id: str, worker_id: str) -> None:
    """Refresh a summarization job lease."""
    response = requests.post(
        f"{API_URL}/summarization-jobs/{job_id}/heartbeat",
        json={"worker_id": worker_id},
        timeout=30,
    )
    response.raise_for_status()


def process_summarization_job(job_id: str, worker_id: str) -> bool:
    """
    Process a summarization job.

    Args:
        job_id: The ID of the summarization job to process

    Returns:
        True if the job was processed successfully, False otherwise
    """
    import time

    start_time = time.time()

    try:
        # Get job details from API
        job = get_job_from_api(job_id)
        transcript_id = job["transcript_id"]

        # Get the transcript from API
        transcript = get_transcript_from_api(transcript_id)
        if not transcript:
            error_details = {"error": f"Transcript not found: {transcript_id}"}
            update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
            return False

        # Get the transcript content
        transcript_content = transcript["content"]

        # Generate summary
        logger.info(f"Generating summary for transcript: {transcript_id}")
        summary_text = create_summary(transcript_content, "manual_transcript")

        # Create summary record via API
        create_summary_api(transcript_id, summary_text)

        # Update transcript status via API
        update_transcript_status_api(transcript_id, "summarized")

        # Mark job as completed
        processing_time = time.time() - start_time
        update_job_status_api(job_id, worker_id, "completed", processing_time=processing_time)

        logger.info(f"Summarization completed for transcript {transcript_id} in {processing_time:.2f} seconds")
        return True

    except Exception as e:
        logger.error(f"Error processing summarization job {job_id}: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")

        # Mark job as failed
        error_details = {"error": str(e), "traceback": traceback.format_exc()}
        update_job_status_api(job_id, worker_id, "failed", error_details=error_details)
        return False
