import argparse
import logging
import os
import sys
import traceback
from typing import Any, Dict

import requests
from translation.config import API_URL
from translation.translation_worker import process_translation_job

from common.messaging import EVENT_JOB_STATUS_CHANGED, EVENT_TRANSCRIPTION_CREATED, RabbitMQClient

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translation")

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()


def get_next_translation_job_api():
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


def handle_transcription_created_event(event_data: Dict[str, Any]):
    """
    Handle a transcription.created event.
    This is optional - we may want to automatically translate new transcriptions.

    Args:
        event_data: The event data
    """
    try:
        transcript_id = event_data.get("transcript_id")
        video_id = event_data.get("video_id")

        if not transcript_id:
            logger.error("Received transcription.created event without transcript_id")
            return

        logger.info(f"Received transcription.created event for transcript {transcript_id} (video {video_id})")

        # For now, we don't automatically create translation jobs
        # This could be enabled in the future if automatic translation is desired
        logger.info("Automatic translation is not enabled, ignoring transcription.created event")

    except Exception as e:
        logger.error(f"Error handling transcription.created event: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def handle_job_status_changed_event(event_data: Dict[str, Any]):
    """
    Handle a job.status.changed event.

    Args:
        event_data: The event data
    """
    try:
        job_type = event_data.get("job_type")
        job_id = event_data.get("job_id")
        status = event_data.get("status")

        if not job_type or not job_id or not status:
            logger.error("Received job.status.changed event with missing data")
            return

        # Only process translation jobs
        if job_type != "translation":
            return

        logger.info(f"Received job.status.changed event for {job_type} job {job_id}: {status}")

        # If the job is pending, process it
        if status == "pending":
            logger.info(f"Processing translation job {job_id}")
            process_translation_job(job_id)

    except Exception as e:
        logger.error(f"Error handling job.status.changed event: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def run_worker():
    """
    Run the translation worker in event-based mode.
    """
    logger.info("Starting translation worker")

    try:
        # Connect to RabbitMQ
        rabbitmq_client.connect()

        # Subscribe to transcription.created events
        rabbitmq_client.subscribe_to_event(
            EVENT_TRANSCRIPTION_CREATED,
            handle_transcription_created_event,
            "translation_transcription_created_queue",
        )

        # Subscribe to job.status.changed events
        rabbitmq_client.subscribe_to_event(
            EVENT_JOB_STATUS_CHANGED,
            handle_job_status_changed_event,
            "translation_job_status_queue",
        )

        # Process any existing pending jobs
        logger.info("Checking for existing pending jobs")
        job = get_next_translation_job_api()
        if job:
            logger.info(f"Found pending translation job {job['id']} for transcript {job['transcript_id']}")
            process_translation_job(job["id"])

        # Start consuming messages
        logger.info("Waiting for events...")
        rabbitmq_client.start_consuming()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        rabbitmq_client.stop_consuming()
        rabbitmq_client.close()

    except Exception as e:
        logger.error(f"Error in worker: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        rabbitmq_client.close()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Translation worker")
    args = parser.parse_args()

    # Run the worker
    run_worker()
