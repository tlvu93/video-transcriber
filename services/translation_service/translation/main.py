import argparse
import logging
import os
import socket
import sys
import threading
import traceback
from typing import Any, Dict

from translation.config import JOB_CLAIM_POLL_SECONDS, JOB_HEARTBEAT_INTERVAL_SECONDS, WORKER_ID
from translation.translation_worker import (
    claim_next_translation_job_api,
    heartbeat_translation_job_api,
    process_translation_job,
)

from common.messaging import EVENT_JOB_STATUS_CHANGED, EVENT_TRANSCRIPTION_CREATED, RabbitMQClient

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("translation")

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()
worker_id = WORKER_ID
stop_event = threading.Event()
wake_event = threading.Event()
job_thread: threading.Thread | None = None
job_thread_lock = threading.Lock()


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

        logger.info("Automatic translation is disabled, transcription.created is only used as a wake-up signal")
        wake_event.set()

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

        # Pending jobs are claimed atomically from the API.
        if status == "pending":
            wake_event.set()

    except Exception as e:
        logger.error(f"Error handling job.status.changed event: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def run_worker():
    """
    Run the translation worker in event-based mode.
    """
    logger.info("Starting translation worker (worker_id=%s on %s)", worker_id, socket.gethostname())

    def heartbeat_loop(job_id: str, heartbeat_stop_event: threading.Event) -> None:
        while not heartbeat_stop_event.wait(JOB_HEARTBEAT_INTERVAL_SECONDS):
            try:
                heartbeat_translation_job_api(job_id, worker_id)
            except Exception as error:
                logger.warning("Failed to heartbeat translation job %s: %s", job_id, error)

    def run_claimed_job(job: Dict[str, Any]) -> None:
        global job_thread

        heartbeat_stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            args=(str(job["id"]), heartbeat_stop_event),
            daemon=True,
            name=f"translation-heartbeat-{job['id']}",
        )
        heartbeat_thread.start()

        try:
            process_translation_job(str(job["id"]), worker_id)
        finally:
            heartbeat_stop_event.set()
            heartbeat_thread.join(timeout=5)
            with job_thread_lock:
                job_thread = None
            wake_event.set()

    def claim_available_job() -> None:
        global job_thread

        with job_thread_lock:
            if job_thread and job_thread.is_alive():
                return

            job = claim_next_translation_job_api(worker_id)
            if not job:
                return

            logger.info("Claimed translation job %s for transcript %s", job["id"], job["transcript_id"])
            job_thread = threading.Thread(
                target=run_claimed_job,
                args=(job,),
                daemon=True,
                name=f"translation-job-{job['id']}",
            )
            job_thread.start()

    def claim_loop() -> None:
        while not stop_event.is_set():
            wake_event.wait(timeout=JOB_CLAIM_POLL_SECONDS)
            wake_event.clear()

            try:
                claim_available_job()
            except Exception as error:
                logger.error("Error claiming translation jobs: %s", error)
                logger.error("Exception traceback: %s", traceback.format_exc())

    claim_thread = threading.Thread(target=claim_loop, daemon=True, name="translation-claim-loop")
    claim_thread.start()

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

        logger.info("Checking for existing pending jobs")
        wake_event.set()

        # Start consuming messages
        logger.info("Waiting for events...")
        rabbitmq_client.start_consuming()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")

    except Exception as e:
        logger.error(f"Error in worker: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")
    finally:
        stop_event.set()
        wake_event.set()
        try:
            rabbitmq_client.stop_consuming()
        except Exception:
            pass
        rabbitmq_client.close()
        claim_thread.join(timeout=5)
        with job_thread_lock:
            active_job_thread = job_thread
        if active_job_thread:
            active_job_thread.join(timeout=5)


if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Translation worker")
    args = parser.parse_args()

    # Run the worker
    run_worker()
