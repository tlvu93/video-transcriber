from __future__ import annotations

import argparse

from backend.app.runtime.bootstrap import bootstrap_service_paths, configure_logging
from backend.app.runtime.single_job_worker import run_single_job_polling_worker


def main() -> None:
    bootstrap_service_paths()
    configure_logging()

    from backend.app.translation.config import (
        JOB_CLAIM_POLL_SECONDS,
        JOB_HEARTBEAT_INTERVAL_SECONDS,
        WORKER_ID,
    )
    from backend.app.translation.translation_worker import (
        claim_next_translation_job_api,
        heartbeat_translation_job_api,
        process_translation_job,
    )

    parser = argparse.ArgumentParser(description="Translation worker")
    parser.parse_args()

    run_single_job_polling_worker(
        worker_name="translation",
        worker_id=WORKER_ID,
        claim_poll_seconds=JOB_CLAIM_POLL_SECONDS,
        heartbeat_interval_seconds=JOB_HEARTBEAT_INTERVAL_SECONDS,
        claim_next_job=claim_next_translation_job_api,
        heartbeat_job=heartbeat_translation_job_api,
        process_job=process_translation_job,
        describe_claimed_job=lambda job: f"transcript {job['transcript_id']}",
    )


if __name__ == "__main__":
    main()
