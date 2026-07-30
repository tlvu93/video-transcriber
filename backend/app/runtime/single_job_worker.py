from __future__ import annotations

import logging
import threading
import time
import traceback
from collections.abc import Callable
from typing import Any

from backend.app.runtime.job_notifications import (
    should_wake_for_job_type,
    start_job_notification_listener,
)

ClaimJobFn = Callable[[str], dict[str, Any] | None]
HeartbeatJobFn = Callable[[str, str], None]
ProcessJobFn = Callable[[str, str], Any]
DescribeJobFn = Callable[[dict[str, Any]], str]


def run_single_job_polling_worker(
    *,
    worker_name: str,
    worker_id: str,
    claim_poll_seconds: int,
    heartbeat_interval_seconds: int,
    claim_next_job: ClaimJobFn,
    heartbeat_job: HeartbeatJobFn,
    process_job: ProcessJobFn,
    describe_claimed_job: DescribeJobFn | None = None,
) -> None:
    logger = logging.getLogger(worker_name)
    stop_event = threading.Event()
    wake_event = threading.Event()
    job_thread: threading.Thread | None = None
    job_thread_lock = threading.Lock()
    notification_thread = start_job_notification_listener(
        listener_name=worker_name,
        stop_event=stop_event,
        wake_event=wake_event,
        should_wake_for_event=lambda event: should_wake_for_job_type(worker_name, event),
    )

    logger.info("Starting %s worker (worker_id=%s)", worker_name, worker_id)

    def heartbeat_loop(job_id: str, heartbeat_stop_event: threading.Event) -> None:
        while not heartbeat_stop_event.wait(heartbeat_interval_seconds):
            try:
                heartbeat_job(job_id, worker_id)
            except Exception as error:
                logger.warning("Failed to heartbeat %s job %s: %s", worker_name, job_id, error)

    def run_claimed_job(job: dict[str, Any]) -> None:
        nonlocal job_thread

        heartbeat_stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=heartbeat_loop,
            args=(str(job["id"]), heartbeat_stop_event),
            daemon=True,
            name=f"{worker_name}-heartbeat-{job['id']}",
        )
        heartbeat_thread.start()

        try:
            process_job(str(job["id"]), worker_id)
        finally:
            heartbeat_stop_event.set()
            heartbeat_thread.join(timeout=5)
            with job_thread_lock:
                job_thread = None
            wake_event.set()

    def claim_available_job() -> None:
        nonlocal job_thread

        with job_thread_lock:
            if job_thread and job_thread.is_alive():
                return

            job = claim_next_job(worker_id)
            if not job:
                return

            job_description = (
                describe_claimed_job(job) if describe_claimed_job else ""
            )
            if job_description:
                logger.info("Claimed %s job %s (%s)", worker_name, job["id"], job_description)
            else:
                logger.info("Claimed %s job %s", worker_name, job["id"])

            job_thread = threading.Thread(
                target=run_claimed_job,
                args=(job,),
                daemon=True,
                name=f"{worker_name}-job-{job['id']}",
            )
            job_thread.start()

    def claim_loop() -> None:
        while not stop_event.is_set():
            wake_event.wait(timeout=claim_poll_seconds)
            wake_event.clear()

            try:
                claim_available_job()
            except Exception as error:
                logger.error("Error claiming %s jobs: %s", worker_name, error)
                logger.error("Exception traceback: %s", traceback.format_exc())

    claim_thread = threading.Thread(
        target=claim_loop,
        daemon=True,
        name=f"{worker_name}-claim-loop",
    )
    claim_thread.start()

    try:
        logger.info(
            "Polling %s jobs every %s seconds with immediate wake-ups after local completions",
            worker_name,
            claim_poll_seconds,
        )
        wake_event.set()

        while not stop_event.is_set():
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    except Exception as error:
        logger.error("Error in %s worker: %s", worker_name, error)
        logger.error("Exception traceback: %s", traceback.format_exc())
    finally:
        stop_event.set()
        wake_event.set()
        if notification_thread:
            notification_thread.join(timeout=5)
        claim_thread.join(timeout=5)
        with job_thread_lock:
            active_job_thread = job_thread
        if active_job_thread:
            active_job_thread.join(timeout=5)
