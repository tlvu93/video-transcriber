from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from backend.app.runtime.config import (
    LIVE_UPDATES_CHANNEL,
    LIVE_UPDATES_NOTIFY_ENABLED,
    LIVE_UPDATES_RECONNECT_SECONDS,
    PSYCOPG_CONNINFO,
)

logger = logging.getLogger("backend.runtime.job_notifications")
WakeEventFilter = Callable[[dict[str, Any]], bool]


def _parse_notification_payload(payload: str) -> dict[str, Any] | None:
    try:
        envelope = json.loads(payload)
    except json.JSONDecodeError:
        logger.warning("Received malformed PostgreSQL notify payload")
        return None

    if not isinstance(envelope, dict):
        return None

    event = envelope.get("event")
    if not isinstance(event, dict):
        return None

    return event


def start_job_notification_listener(
    *,
    listener_name: str,
    stop_event: threading.Event,
    wake_event: threading.Event,
    should_wake_for_event: WakeEventFilter,
) -> threading.Thread | None:
    if not LIVE_UPDATES_NOTIFY_ENABLED:
        logger.info("Live update notifications disabled; %s will use polling only", listener_name)
        return None

    async def _run_listener() -> None:
        import psycopg

        while not stop_event.is_set():
            try:
                connection = await psycopg.AsyncConnection.connect(
                    PSYCOPG_CONNINFO,
                    autocommit=True,
                )
                async with connection:
                    async with connection.cursor() as cursor:
                        await cursor.execute(f"LISTEN {LIVE_UPDATES_CHANNEL}")

                    logger.info(
                        "%s subscribed to PostgreSQL notification channel '%s'",
                        listener_name,
                        LIVE_UPDATES_CHANNEL,
                    )

                    while not stop_event.is_set():
                        async for notification in connection.notifies(timeout=1.0, stop_after=1):
                            event = _parse_notification_payload(notification.payload)
                            if event is None:
                                continue

                            if should_wake_for_event(event):
                                wake_event.set()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "%s notification listener disconnected; retrying in %s seconds",
                    listener_name,
                    LIVE_UPDATES_RECONNECT_SECONDS,
                )
                await asyncio.sleep(LIVE_UPDATES_RECONNECT_SECONDS)

    def _runner() -> None:
        try:
            asyncio.run(_run_listener())
        except Exception:
            logger.exception("%s notification listener stopped unexpectedly", listener_name)

    thread = threading.Thread(
        target=_runner,
        daemon=True,
        name=f"{listener_name}-notify-listener",
    )
    thread.start()
    return thread


def should_wake_for_job_type(worker_name: str, event: dict[str, Any]) -> bool:
    if event.get("type") != "job.status.changed":
        return False

    return str(event.get("job_type")) == worker_name
