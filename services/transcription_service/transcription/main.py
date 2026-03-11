import argparse
import logging
import os
import socket
import sys
import threading
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, Set

from transcription.api_client import (
    claim_next_transcription_job_api,
    heartbeat_transcription_job_api,
)
from transcription.config import JOB_CLAIM_POLL_SECONDS, JOB_HEARTBEAT_INTERVAL_SECONDS, WORKER_ID
from transcription.transcription_worker import process_transcription_job

from common.messaging import EVENT_JOB_STATUS_CHANGED, EVENT_VIDEO_CREATED, RabbitMQClient

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("transcription")

# Initialize RabbitMQ client
rabbitmq_client = RabbitMQClient()

wake_event = threading.Event()
stop_event = threading.Event()
executor: ThreadPoolExecutor | None = None
worker_id = WORKER_ID
max_parallel_jobs = 1
active_futures: Set[Future[bool]] = set()
active_futures_lock = threading.Lock()


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

        wake_event.set()

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

        logger.info(f"Received job.status.changed event for {job_type} job {job_id}: {status}")

        # Pending jobs are now claimed atomically from the API.
        if status == "pending":
            wake_event.set()

    except Exception as e:
        logger.error(f"Error handling job.status.changed event: {str(e)}")
        logger.error(f"Exception traceback: {traceback.format_exc()}")


def available_capacity() -> int:
    """Return how many jobs can still be claimed by this worker process."""
    with active_futures_lock:
        return max_parallel_jobs - len(active_futures)


def heartbeat_loop(job_id: str, heartbeat_stop_event: threading.Event) -> None:
    """Refresh the active lease for a claimed job until processing stops."""
    while not heartbeat_stop_event.wait(JOB_HEARTBEAT_INTERVAL_SECONDS):
        try:
            heartbeat_transcription_job_api(job_id, worker_id)
        except Exception as error:
            logger.warning("Failed to heartbeat transcription job %s: %s", job_id, error)


def run_claimed_job(job: Dict[str, Any]) -> bool:
    """Process a claimed job while keeping its lease alive."""
    heartbeat_stop_event = threading.Event()
    heartbeat_thread = threading.Thread(
        target=heartbeat_loop,
        args=(str(job["id"]), heartbeat_stop_event),
        daemon=True,
        name=f"transcription-heartbeat-{job['id']}",
    )
    heartbeat_thread.start()

    try:
        return process_transcription_job(str(job["id"]), worker_id)
    finally:
        heartbeat_stop_event.set()
        heartbeat_thread.join(timeout=5)


def on_job_finished(future: Future[bool]) -> None:
    """Track active futures and trigger another claim pass when a slot frees up."""
    with active_futures_lock:
        active_futures.discard(future)

    try:
        future.result()
    except Exception as error:
        logger.error("Transcription worker future failed: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())
    finally:
        wake_event.set()


def submit_claimed_job(job: Dict[str, Any]) -> None:
    """Submit a claimed job to the thread pool."""
    assert executor is not None
    future = executor.submit(run_claimed_job, job)
    with active_futures_lock:
        active_futures.add(future)
    future.add_done_callback(on_job_finished)


def claim_available_jobs() -> None:
    """Claim as many jobs as possible without exceeding worker capacity."""
    while not stop_event.is_set() and available_capacity() > 0:
        job = claim_next_transcription_job_api(worker_id)
        if not job:
            return

        logger.info("Claimed transcription job %s for video %s", job["id"], job["video_id"])
        submit_claimed_job(job)


def claim_loop() -> None:
    """Run an event-driven claim loop with a short polling fallback."""
    while not stop_event.is_set():
        wake_event.wait(timeout=JOB_CLAIM_POLL_SECONDS)
        wake_event.clear()

        try:
            claim_available_jobs()
        except Exception as error:
            logger.error("Error claiming transcription jobs: %s", error)
            logger.error("Exception traceback: %s", traceback.format_exc())


def run_worker(max_workers: int = 1):
    """
    Run the transcription worker in event-based mode.

    Args:
        max_workers: Maximum number of worker threads to use
    """
    global executor
    global max_parallel_jobs

    max_parallel_jobs = max_workers
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="transcription-job")
    claim_thread = threading.Thread(target=claim_loop, daemon=True, name="transcription-claim-loop")
    claim_thread.start()

    logger.info(
        "Starting transcription worker with %s workers (worker_id=%s on %s)",
        max_workers,
        worker_id,
        socket.gethostname(),
    )

    try:
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
        if executor is not None:
            executor.shutdown(wait=True)


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
