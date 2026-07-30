"""A minimal in-process sliding-window rate limiter.

Intentionally simple: per-process, in-memory state keyed by an arbitrary
string (typically the client IP). This is enough to blunt accidental or
abusive bursts of expensive requests (video uploads, YouTube downloads,
which each spawn a transcription job) on a single-instance deployment. It is
not a substitute for a shared limiter (e.g. Redis-backed) if this API is
ever run with multiple worker processes/replicas behind a load balancer.
"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindowRateLimiter:
    def __init__(self, *, max_requests: int, window_seconds: float = 60.0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Record a hit for `key` and return whether it is within the allowed rate."""
        if self.max_requests <= 0:
            return True

        current_time = now if now is not None else time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            cutoff = current_time - self.window_seconds
            while hits and hits[0] < cutoff:
                hits.popleft()

            if len(hits) >= self.max_requests:
                return False

            hits.append(current_time)
            return True
