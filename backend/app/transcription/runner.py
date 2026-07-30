from __future__ import annotations

import argparse
import logging
import threading
import time
import traceback
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from backend.app.runtime.bootstrap import bootstrap_service_paths, configure_logging
from backend.app.runtime.job_notifications import (
    should_wake_for_job_type,
    start_job_notification_listener,
)

bootstrap_service_paths()
configure_logging()

from backend.app.transcription.api_client import (  # noqa: E402
    claim_next_transcription_job_api,
    heartbeat_transcription_job_api,
)
from backend.app.transcription.config import (  # noqa: E402
    JOB_CLAIM_POLL_SECONDS,
    JOB_HEARTBEAT_INTERVAL_SECONDS,
    WORKER_ID,
)
from backend.app.transcription.transcription_worker import process_transcription_job  # noqa: E402

logger = logging.getLogger("transcription")
wake_event = threading.Event()
stop_event = threading.Event()
executor: ThreadPoolExecutor | None = None
worker_id = WORKER_ID
max_parallel_jobs = 1
active_futures: set[Future[bool]] = set()
active_futures_lock = threading.Lock()


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


def run_claimed_job(job: dict[str, Any]) -> bool:
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


def submit_claimed_job(job: dict[str, Any]) -> None:
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
    """Poll the API for claimable jobs and wake immediately when local capacity changes."""
    while not stop_event.is_set():
        wake_event.wait(timeout=JOB_CLAIM_POLL_SECONDS)
        wake_event.clear()

        try:
            claim_available_jobs()
        except Exception as error:
            logger.error("Error claiming transcription jobs: %s", error)
            logger.error("Exception traceback: %s", traceback.format_exc())


def run_worker(max_workers: int = 1) -> None:
    """Run the transcription worker in event-based mode."""
    global executor
    global max_parallel_jobs

    max_parallel_jobs = max_workers
    executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="transcription-job")
    claim_thread = threading.Thread(target=claim_loop, daemon=True, name="transcription-claim-loop")
    claim_thread.start()
    notification_thread = start_job_notification_listener(
        listener_name="transcription",
        stop_event=stop_event,
        wake_event=wake_event,
        should_wake_for_event=lambda event: should_wake_for_job_type("transcription", event),
    )

    logger.info(
        "Starting transcription worker with %s workers (worker_id=%s)",
        max_workers,
        worker_id,
    )

    try:
        logger.info(
            "Polling transcription jobs every %s seconds with immediate wake-ups after local completions",
            JOB_CLAIM_POLL_SECONDS,
        )
        wake_event.set()

        while not stop_event.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as error:
        logger.error("Error in worker: %s", error)
        logger.error("Exception traceback: %s", traceback.format_exc())
    finally:
        stop_event.set()
        wake_event.set()
        if notification_thread:
            notification_thread.join(timeout=5)
        claim_thread.join(timeout=5)
        if executor is not None:
            executor.shutdown(wait=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcription worker")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Maximum number of worker threads to use",
    )
    args = parser.parse_args()
    run_worker(args.max_workers)


if __name__ == "__main__":
    main()
