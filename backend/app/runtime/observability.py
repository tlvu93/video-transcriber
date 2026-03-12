from __future__ import annotations

import contextvars
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any


REQUEST_ID_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "video_transcriber_request_id",
    default="-",
)

STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def bind_request_id(request_id: str) -> contextvars.Token[str]:
    return REQUEST_ID_CONTEXT.set(request_id)


def reset_request_id(token: contextvars.Token[str]) -> None:
    REQUEST_ID_CONTEXT.reset(token)


def get_request_id() -> str:
    return REQUEST_ID_CONTEXT.get()


def get_service_name() -> str:
    configured_name = os.environ.get("SERVICE_NAME", "").strip()
    return configured_name or "video-transcriber"


def get_log_level() -> int:
    configured_level = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    return getattr(logging, configured_level, logging.INFO)


def use_structured_logs() -> bool:
    return os.environ.get("LOG_FORMAT", "json").strip().lower() != "text"


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        if not hasattr(record, "service"):
            record.service = get_service_name()
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": getattr(record, "service", get_service_name()),
            "request_id": getattr(record, "request_id", get_request_id()),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        for key, value in record.__dict__.items():
            if key in STANDARD_LOG_RECORD_FIELDS or key in payload:
                continue
            payload[key] = _normalize_log_value(value)

        return json.dumps(payload, ensure_ascii=True, default=str)


def build_log_formatter() -> logging.Formatter:
    if use_structured_logs():
        return JsonLogFormatter()
    return logging.Formatter(
        "%(asctime)s - %(service)s - %(name)s - %(levelname)s - %(request_id)s - %(message)s"
    )


def _normalize_log_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {str(key): _normalize_log_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_normalize_log_value(item) for item in value]
    return str(value)
