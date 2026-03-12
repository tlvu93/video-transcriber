from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from backend.app.runtime.observability import (
    RequestContextFilter,
    build_log_formatter,
    get_log_level,
)
SERVICE_PACKAGE_DIRS = (
    Path("services/api_service"),
    Path("services/transcription_service"),
    Path("services/summarization_service"),
    Path("services/translation_service"),
    Path("services/watcher_service"),
)


def get_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_app_data_dir() -> Path:
    configured_data_dir = os.environ.get("APP_DATA_DIR")
    if configured_data_dir:
        return Path(configured_data_dir).expanduser().resolve()

    return get_repo_root() / "data"


def bootstrap_service_paths() -> Path:
    repo_root = get_repo_root()
    candidate_paths = [repo_root, *(repo_root / path for path in SERVICE_PACKAGE_DIRS)]

    for candidate_path in candidate_paths:
        candidate = str(candidate_path)
        if candidate not in sys.path:
            sys.path.insert(0, candidate)

    return repo_root


def configure_logging(level: int = logging.INFO) -> None:
    configured_level = level if level != logging.INFO else get_log_level()
    formatter = build_log_formatter()
    context_filter = RequestContextFilter()

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(configured_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(configured_level)
    handler.setFormatter(formatter)
    handler.addFilter(context_filter)
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logger_instance = logging.getLogger(logger_name)
        logger_instance.handlers.clear()
        logger_instance.setLevel(configured_level)
        logger_instance.propagate = True
