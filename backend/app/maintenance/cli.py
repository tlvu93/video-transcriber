from __future__ import annotations

import argparse
import logging

from backend.app.runtime.bootstrap import bootstrap_service_paths, configure_logging


logger = logging.getLogger("backend.maintenance")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Video Transcriber maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    purge_metrics_parser = subparsers.add_parser(
        "purge-metrics",
        help="Delete operational metric samples older than the specified number of hours",
    )
    purge_metrics_parser.add_argument(
        "--older-than-hours",
        type=int,
        default=24 * 30,
        help="Delete metric events older than this many hours",
    )

    subparsers.add_parser(
        "rebuild-search-index",
        help="Rebuild transcript segment search rows from canonical transcript segment rows",
    )

    return parser


def purge_metrics(older_than_hours: int) -> None:
    from backend.app.runtime.metrics import purge_metric_events

    deleted_count = purge_metric_events(older_than_hours=older_than_hours)
    logger.info(
        "Purged %s operational metric event(s) older than %s hours",
        deleted_count,
        older_than_hours,
    )


def rebuild_search_index() -> None:
    from backend.app.persistence.database import SessionLocal
    from backend.app.persistence.search_index import rebuild_all_transcript_search_rows

    with SessionLocal() as db:
        rebuild_all_transcript_search_rows(db)

    logger.info("Rebuilt transcript search index rows")


def main() -> None:
    bootstrap_service_paths()
    configure_logging()

    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "purge-metrics":
        purge_metrics(args.older_than_hours)
        return

    if args.command == "rebuild-search-index":
        rebuild_search_index()
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
