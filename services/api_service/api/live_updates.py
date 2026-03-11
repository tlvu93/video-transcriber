import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from fastapi import Request

logger = logging.getLogger("live_updates")

KEEPALIVE_INTERVAL_SECONDS = 15
QUEUE_SIZE = 100


@dataclass
class LiveUpdateSubscriber:
    filters: Dict[str, str]
    queue: asyncio.Queue[Dict[str, Any]] = field(
        default_factory=lambda: asyncio.Queue(maxsize=QUEUE_SIZE)
    )


class LiveUpdateManager:
    def __init__(self) -> None:
        self._subscribers: List[LiveUpdateSubscriber] = []
        self._lock = asyncio.Lock()

    async def publish(self, event: Dict[str, Any]) -> None:
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

    async def subscribe(self, filters: Dict[str, str]) -> LiveUpdateSubscriber:
        subscriber = LiveUpdateSubscriber(filters=filters)
        async with self._lock:
            self._subscribers.append(subscriber)
        return subscriber

    async def unsubscribe(self, subscriber: LiveUpdateSubscriber) -> None:
        async with self._lock:
            if subscriber in self._subscribers:
                self._subscribers.remove(subscriber)

    async def stream(
        self,
        request: Request,
        filters: Dict[str, str],
    ) -> AsyncIterator[str]:
        subscriber = await self.subscribe(filters)
        yield self._format_event({"type": "live.connected"})

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        subscriber.queue.get(),
                        timeout=KEEPALIVE_INTERVAL_SECONDS,
                    )
                    yield self._format_event(event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await self.unsubscribe(subscriber)

    def _matches_filters(self, event: Dict[str, Any], filters: Dict[str, str]) -> bool:
        if not filters:
            return True

        return any(
            event.get(key) == value
            for key, value in filters.items()
            if value
        )

    def _format_event(self, event: Dict[str, Any]) -> str:
        return f"data: {json.dumps(event)}\n\n"


def build_live_update_filters(
    video_id: Optional[str] = None,
    transcript_id: Optional[str] = None,
) -> Dict[str, str]:
    filters: Dict[str, str] = {}

    if video_id:
        filters["video_id"] = video_id

    if transcript_id:
        filters["transcript_id"] = transcript_id

    return filters


live_update_manager = LiveUpdateManager()
