from common.messaging import (
    RabbitMQClient,
    EVENT_VIDEO_CREATED,
    EVENT_JOB_STATUS_CHANGED,
)
from transcription.queue_manager import TranscriptionQueueManager
from transcription.transcription_worker import process_transcription_job
from transcription.api_client import (
    api_request,
    get_next_transcription_job_api,
    get_all_pending_transcription_jobs_api,
    get_job_from_api,
)
import argparse
import logging
import traceback
import os
import sys
from typing import Dict, Any


# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("transcription")

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()

# Initialize queue manager (will be set in main)
queue_manager = None


def handle_video_created_event(event_data: Dict[str, Any]):
    """
    Handle a video.created event.

    Args:
        event_data: The event data
    """
    try:
        video_id = event_data.get("video_id")
        filename = event_data.get("filename")

        if not video_id:
            logger.error("Received video.created event without video_id")
            return

        logger.info(f"Received video.created event for video {video_id} ({filename})")

        # Get the next transcription job from the API
        # The API service should have already created a transcription job for this video
        job = get_next_transcription_job_api()

        if job and job["video_id"] == video_id:
            logger.info(
                f"Adding transcription job {job['id']} for video {video_id} to queue"
            )
            queue_manager.add_job(job)
        else:
            logger.warning(f"No transcription job found for video {video_id}")

    except Exception as e:
        logger.error(f"Error handling video.created event: {str(e)}")
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

        # Only process transcription jobs
        if job_type != "transcription":
            return

        logger.info(
            f"Received job.status.changed event for {job_type} job {job_id}: {status}"
        )

        # If the job is pending, add it to the queue
        if status == "pending":
            # Get job details
            try:
                job = get_job_from_api(job_id)
                logger.info(f"Adding transcription job {job_id} to queue")
                queue_manager.add_job(job)
            except Exception as e:
                logger.error(f"Error getting job details: {str(e)}")

    except Exception as e:
        logger.error(f"Error handling job.status.changed event: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def run_worker(max_workers: int = 1):
    """
    Run the transcription worker in event-based mode.

    Args:
        max_workers: Maximum number of worker threads to use
    """
    global queue_manager

    logger.info(f"Starting transcription worker with {max_workers} workers")

    try:
        # Initialize queue manager
        queue_manager = TranscriptionQueueManager(max_workers=max_workers)
        queue_manager.start(process_transcription_job)

        # Connect to RabbitMQ
        rabbitmq_client.connect()

        # Subscribe to video.created events
        rabbitmq_client.subscribe_to_event(
            EVENT_VIDEO_CREATED,
            handle_video_created_event,
            "transcription_video_created_queue",
        )

        # Subscribe to job.status.changed events
        rabbitmq_client.subscribe_to_event(
            EVENT_JOB_STATUS_CHANGED,
            handle_job_status_changed_event,
            "transcription_job_status_queue",
        )

        # TODO: Check if transcription jobs should pull from the API or if they should be pushed by the API service
        # Process all existing pending jobs
        logger.info("Checking for existing pending jobs")
        jobs = get_all_pending_transcription_jobs_api()
        if jobs:
            logger.info(f"Found {len(jobs)} pending transcription jobs")
            for job in jobs:
                logger.info(
                    f"Adding transcription job {job['id']} for video {job['video_id']} to queue"
                )
                queue_manager.add_job(job)
        else:
            logger.info("No pending transcription jobs found")

        # Start consuming messages
        logger.info("Waiting for events...")
        rabbitmq_client.start_consuming()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
        queue_manager.stop()
        rabbitmq_client.stop_consuming()
        rabbitmq_client.close()

    except Exception as e:
        logger.error(f"Error in worker: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        if queue_manager:
            queue_manager.stop()
        rabbitmq_client.close()


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcription worker")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Maximum number of worker threads to use",
    )
    args = parser.parse_args()

    # Run the worker
    run_worker(args.max_workers)
