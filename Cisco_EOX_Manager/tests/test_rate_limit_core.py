from __future__ import annotations

from app.core.rate_limit import InMemorySlidingWindowRateLimiter


def test_in_memory_rate_limiter_rejects_after_limit():
    limiter = InMemorySlidingWindowRateLimiter()
    assert limiter.check(key="ip:test", limit=2, window_seconds=60, now=100.0)[0] is True
    assert limiter.check(key="ip:test", limit=2, window_seconds=60, now=101.0)[0] is True
    allowed, remaining, retry_after = limiter.check(key="ip:test", limit=2, window_seconds=60, now=102.0)
    assert allowed is False
    assert remaining == 0
    assert retry_after > 0


def test_in_memory_rate_limiter_window_expires():
    limiter = InMemorySlidingWindowRateLimiter()
    assert limiter.check(key="ip:test", limit=1, window_seconds=10, now=100.0)[0] is True
    assert limiter.check(key="ip:test", limit=1, window_seconds=10, now=105.0)[0] is False
    assert limiter.check(key="ip:test", limit=1, window_seconds=10, now=111.0)[0] is True
