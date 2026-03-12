from __future__ import annotations

import argparse

from backend.app.runtime.bootstrap import bootstrap_service_paths, configure_logging
from backend.app.runtime.single_job_worker import run_single_job_polling_worker


def main() -> None:
    bootstrap_service_paths()
    configure_logging()

    from backend.app.summarization.config import (
        JOB_CLAIM_POLL_SECONDS,
        JOB_HEARTBEAT_INTERVAL_SECONDS,
        WORKER_ID,
    )
    from backend.app.summarization.worker import (
        claim_next_summarization_job_api,
        heartbeat_summarization_job_api,
        process_summarization_job,
    )

    parser = argparse.ArgumentParser(description="Summarization worker")
    parser.parse_args()

    run_single_job_polling_worker(
        worker_name="summarization",
        worker_id=WORKER_ID,
        claim_poll_seconds=JOB_CLAIM_POLL_SECONDS,
        heartbeat_interval_seconds=JOB_HEARTBEAT_INTERVAL_SECONDS,
        claim_next_job=claim_next_summarization_job_api,
        heartbeat_job=heartbeat_summarization_job_api,
        process_job=process_summarization_job,
        describe_claimed_job=lambda job: f"transcript {job['transcript_id']}",
    )


if __name__ == "__main__":
    main()
