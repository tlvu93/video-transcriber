from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from backend.app.persistence.database import engine
from backend.app.runtime.config import (
    LIVE_UPDATES_CHANNEL,
    LIVE_UPDATES_NOTIFY_ENABLED,
    LIVE_UPDATES_RECONNECT_SECONDS,
    PSYCOPG_CONNINFO,
)

logger = logging.getLogger("live_updates")

KEEPALIVE_INTERVAL_SECONDS = 15
QUEUE_SIZE = 100
PG_NOTIFY_MAX_PAYLOAD_BYTES = 7900


@dataclass
class LiveUpdateSubscriber:
    filters: dict[str, str]
    queue: asyncio.Queue[dict[str, Any]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_SIZE)
    )


class LiveUpdateManager:
    def __init__(self) -> None:
        self._subscribers: list[LiveUpdateSubscriber] = []
        self._lock = asyncio.Lock()
        self._instance_id = uuid4().hex
        self._listener_task: asyncio.Task[None] | None = None

    async def publish(self, event: dict[str, Any]) -> None:
        await self._broadcast_local(event)
        await self._publish_backplane(event)

    async def start(self) -> None:
        if not LIVE_UPDATES_NOTIFY_ENABLED:
            logger.info("PostgreSQL live update backplane is disabled")
            return

        if self._listener_task and not self._listener_task.done():
            return

        self._listener_task = asyncio.create_task(
            self._run_notification_listener(),
            name="video-transcriber-live-updates",
        )

    async def stop(self) -> None:
        if not self._listener_task:
            return

        self._listener_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._listener_task
        self._listener_task = None

    async def subscribe(self, filters: dict[str, str]) -> LiveUpdateSubscriber:
        subscriber = LiveUpdateSubscriber(filters=filters)
        async with self._lock:
            self._subscribers.append(subscriber)
        return subscriber

    async def unsubscribe(self, subscriber: LiveUpdateSubscriber) -> None:
        async with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    async def _broadcast_local(self, event: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers)

        for subscriber in subscribers:
            if not self._matches_filters(event, subscriber.filters):
                continue

            if subscriber.queue.full():
                try:
                    subscriber.queue.get_nowait()
                except asyncio.QueueEmpty:
                    logger.debug("Live update queue was empty during overflow handling")

            subscriber.queue.put_nowait(event)

    async def _publish_backplane(self, event: dict[str, Any]) -> None:
        if not LIVE_UPDATES_NOTIFY_ENABLED:
            return

        payload = json.dumps(
            {"event": event, "publisher_id": self._instance_id},
            default=self._json_default,
            separators=(",", ":"),
        )

        if len(payload.encode("utf-8")) > PG_NOTIFY_MAX_PAYLOAD_BYTES:
            logger.warning("Live update payload exceeded PostgreSQL NOTIFY limit; skipping backplane publish")
            return

        def _notify() -> None:
            with engine.begin() as connection:
                connection.execute(
                    text("SELECT pg_notify(:channel, :payload)"),
                    {"channel": LIVE_UPDATES_CHANNEL, "payload": payload},
                )

        await asyncio.to_thread(_notify)

    def _matches_filters(self, event: dict[str, Any], filters: dict[str, str]) -> bool:
        if not filters:
            return True

        return any(
            event.get(key) == value
            for key, value in filters.items()
            if value
        )

    async def _run_notification_listener(self) -> None:
        import psycopg

        while True:
            try:
                connection = await psycopg.AsyncConnection.connect(
                    PSYCOPG_CONNINFO,
                    autocommit=True,
                )
                async with connection:
                    async with connection.cursor() as cursor:
                        await cursor.execute(f"LISTEN {LIVE_UPDATES_CHANNEL}")

                    logger.info(
                        "Subscribed to PostgreSQL live update channel '%s'",
                        LIVE_UPDATES_CHANNEL,
                    )

                    async for notification in connection.notifies():
                        event = self._parse_backplane_event(notification.payload)
                        if event is None:
                            continue

                        await self._broadcast_local(event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Live update listener disconnected; retrying in %s seconds",
                    LIVE_UPDATES_RECONNECT_SECONDS,
                )
                await asyncio.sleep(LIVE_UPDATES_RECONNECT_SECONDS)

    def _parse_backplane_event(self, payload: str) -> dict[str, Any] | None:
        try:
            envelope = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Received malformed live update payload from PostgreSQL")
            return None

        if not isinstance(envelope, dict):
            return None

        if envelope.get("publisher_id") == self._instance_id:
            return None

        event = envelope.get("event")
        if not isinstance(event, dict):
            return None

        return event

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, (date, datetime)):
            return value.isoformat()

        if isinstance(value, Decimal):
            return float(value)

        return str(value)


def format_live_update_sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def build_live_update_filters(
    video_id: str | None = None,
    transcript_id: str | None = None,
) -> dict[str, str]:
    filters: dict[str, str] = {}

    if video_id:
        filters["video_id"] = video_id

    if transcript_id:
        filters["transcript_id"] = transcript_id

    return filters


live_update_manager = LiveUpdateManager()
