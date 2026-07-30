from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from backend.app.runtime.live_updates import live_update_manager

EVENT_VIDEO_UPDATED = "video.updated"
EVENT_TRANSCRIPT_UPDATED = "transcript.updated"
EVENT_TRANSLATED_TRANSCRIPT_UPDATED = "translated_transcript.updated"
EVENT_VIDEO_CREATED = "video.created"
EVENT_TRANSCRIPTION_CREATED = "transcription.created"
EVENT_SUMMARY_CREATED = "summary.created"
EVENT_TRANSLATION_CREATED = "translation.created"
EVENT_JOB_STATUS_CHANGED = "job.status.changed"


async def publish_live_update(event_type: str, **payload: Any) -> None:
    await live_update_manager.publish(
        {
            "type": event_type,
            **{key: value for key, value in payload.items() if value is not None},
        }
    )


async def publish_job_live_update(
    job_type: str,
    job_id: str,
    status: str,
    *,
    video_id: str | None = None,
    transcript_id: str | None = None,
    worker_id: str | None = None,
    lease_expires_at: datetime | None = None,
    progress: float | None = None,
    attempt_count: int | None = None,
) -> None:
    await publish_live_update(
        EVENT_JOB_STATUS_CHANGED,
        job_id=job_id,
        job_type=job_type,
        status=status,
        transcript_id=transcript_id,
        video_id=video_id,
        worker_id=worker_id,
        lease_expires_at=lease_expires_at.isoformat() if lease_expires_at else None,
        progress=progress,
        attempt_count=attempt_count,
    )


def _dispatch_sync(coroutine: Any) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coroutine)
        return

    loop.create_task(coroutine)


def publish_live_update_sync(event_type: str, **payload: Any) -> None:
    _dispatch_sync(publish_live_update(event_type, **payload))


def publish_job_live_update_sync(
    job_type: str,
    job_id: str,
    status: str,
    *,
    video_id: str | None = None,
    transcript_id: str | None = None,
    worker_id: str | None = None,
    lease_expires_at: datetime | None = None,
    progress: float | None = None,
    attempt_count: int | None = None,
) -> None:
    _dispatch_sync(
        publish_job_live_update(
            job_type,
            job_id,
            status,
            video_id=video_id,
            transcript_id=transcript_id,
            worker_id=worker_id,
            lease_expires_at=lease_expires_at,
            progress=progress,
            attempt_count=attempt_count,
        )
    )
