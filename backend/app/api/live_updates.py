from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator, Dict

from fastapi import Request, WebSocket, WebSocketDisconnect

from backend.app.runtime.live_updates import (
    KEEPALIVE_INTERVAL_SECONDS,
    build_live_update_filters,
    format_live_update_sse,
    live_update_manager as runtime_live_update_manager,
)

logger = logging.getLogger("live_updates")


class ApiLiveUpdateManager:
    def __init__(self) -> None:
        self._runtime_manager = runtime_live_update_manager

    def __getattr__(self, name: str):
        return getattr(self._runtime_manager, name)

    async def stream(
        self,
        request: Request,
        filters: Dict[str, str],
    ) -> AsyncIterator[str]:
        subscriber = await self._runtime_manager.subscribe(filters)
        yield format_live_update_sse({"type": "live.connected"})

        try:
            while True:
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(
                        subscriber.queue.get(),
                        timeout=KEEPALIVE_INTERVAL_SECONDS,
                    )
                    yield format_live_update_sse(event)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await self._runtime_manager.unsubscribe(subscriber)

    async def stream_websocket(
        self,
        websocket: WebSocket,
        filters: Dict[str, str],
    ) -> None:
        subscriber = await self._runtime_manager.subscribe(filters)
        await websocket.accept()
        await websocket.send_json({"type": "live.connected"})

        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        subscriber.queue.get(),
                        timeout=KEEPALIVE_INTERVAL_SECONDS,
                    )
                except asyncio.TimeoutError:
                    await websocket.send_json({"type": "live.keepalive"})
                    continue

                await websocket.send_json(event)
        except WebSocketDisconnect:
            logger.debug("Live update websocket disconnected")
        finally:
            await self._runtime_manager.unsubscribe(subscriber)


live_update_manager = ApiLiveUpdateManager()
