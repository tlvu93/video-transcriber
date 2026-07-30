"""Unit tests for the sliding-window rate limiter used to guard expensive,
job-triggering endpoints (`POST /videos/`, `POST /videos/youtube`)."""

from __future__ import annotations

from backend.app.runtime.rate_limit import SlidingWindowRateLimiter


def test_allows_up_to_the_configured_limit():
    limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=60.0)
    assert limiter.allow("client-a", now=0.0)
    assert limiter.allow("client-a", now=1.0)
    assert limiter.allow("client-a", now=2.0)
    assert not limiter.allow("client-a", now=3.0)


def test_window_expires_old_hits():
    limiter = SlidingWindowRateLimiter(max_requests=2, window_seconds=10.0)
    assert limiter.allow("client-a", now=0.0)
    assert limiter.allow("client-a", now=1.0)
    assert not limiter.allow("client-a", now=2.0)

    # Once the window has fully elapsed, the earlier hits should no longer count.
    assert limiter.allow("client-a", now=11.0)


def test_keys_are_independent():
    limiter = SlidingWindowRateLimiter(max_requests=1, window_seconds=60.0)
    assert limiter.allow("client-a", now=0.0)
    assert not limiter.allow("client-a", now=0.0)
    assert limiter.allow("client-b", now=0.0)


def test_non_positive_limit_disables_limiting():
    limiter = SlidingWindowRateLimiter(max_requests=0, window_seconds=60.0)
    for i in range(100):
        assert limiter.allow("client-a", now=float(i))
