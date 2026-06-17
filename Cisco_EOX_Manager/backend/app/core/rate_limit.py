from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Deque

from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


@dataclass(frozen=True)
class RateLimitSettings:
    enabled: bool
    read_per_minute: int
    write_per_minute: int
    autopop_jobs_per_hour: int
    exempt_paths: tuple[str, ...]


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def _int_env(name: str, default: int, *, minimum: int = 1, maximum: int = 100000) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return max(minimum, min(maximum, value))


def get_rate_limit_settings() -> RateLimitSettings:
    raw_exempt = os.getenv(
        "EOX_RATE_LIMIT_EXEMPT_PATHS",
        "/health,/api/health,/docs,/redoc,/openapi.json,/assets",
    )
    exempt = tuple(item.strip() for item in raw_exempt.split(",") if item.strip())
    return RateLimitSettings(
        enabled=_bool_env("EOX_RATE_LIMIT_ENABLED", True),
        read_per_minute=_int_env("EOX_RATE_LIMIT_READ_PER_MINUTE", 240, maximum=20000),
        write_per_minute=_int_env("EOX_RATE_LIMIT_WRITE_PER_MINUTE", 60, maximum=5000),
        autopop_jobs_per_hour=_int_env("EOX_RATE_LIMIT_AUTOPOP_JOBS_PER_HOUR", 12, maximum=1000),
        exempt_paths=exempt,
    )


class InMemorySlidingWindowRateLimiter:
    """Small-process in-memory rate limiter.

    This is intentionally simple and dependency-free. It protects home-lab and
    single-container deployments from browser loops, accidental script floods,
    and repeated Auto_Pop clicks. For multi-replica production, put a reverse
    proxy or Redis-backed limiter in front of the API.
    """

    def __init__(self) -> None:
        self._hits: dict[str, Deque[float]] = defaultdict(deque)
        self._last_cleanup = 0.0

    def check(self, *, key: str, limit: int, window_seconds: int, now: float | None = None) -> tuple[bool, int, int]:
        now = now if now is not None else time.monotonic()
        cutoff = now - window_seconds
        bucket = self._hits[key]
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        remaining = max(0, limit - len(bucket))
        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window_seconds - now)) if bucket else window_seconds
            return False, remaining, retry_after
        bucket.append(now)
        remaining = max(0, limit - len(bucket))
        self._cleanup(now)
        return True, remaining, 0

    def _cleanup(self, now: float) -> None:
        if now - self._last_cleanup < 120:
            return
        self._last_cleanup = now
        cutoff = now - 3600
        for key in list(self._hits.keys()):
            bucket = self._hits[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                self._hits.pop(key, None)


_LIMITER = InMemorySlidingWindowRateLimiter()


def _client_key(request: Request) -> str:
    token = request.headers.get("authorization") or request.headers.get("x-eox-admin-token") or ""
    if token:
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
        return f"token:{token_hash}"
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    host = forwarded or (request.client.host if request.client else "unknown")
    return f"ip:{host}"


def _is_exempt(path: str, settings: RateLimitSettings) -> bool:
    return any(path == item or path.startswith(f"{item}/") for item in settings.exempt_paths)


def _bucket_for(request: Request, settings: RateLimitSettings) -> tuple[str, int, int, str]:
    path = request.url.path
    base = _client_key(request)
    if request.method.upper() == "POST" and path == "/api/autopop/jobs":
        return f"{base}:autopop", settings.autopop_jobs_per_hour, 3600, "autopop"
    if request.method.upper() in {"GET", "HEAD"}:
        return f"{base}:read", settings.read_per_minute, 60, "read"
    return f"{base}:write", settings.write_per_minute, 60, "write"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_rate_limit_settings()
        if (
            not settings.enabled
            or request.method.upper() == "OPTIONS"
            or _is_exempt(request.url.path, settings)
        ):
            return await call_next(request)

        bucket_key, limit, window_seconds, bucket_name = _bucket_for(request, settings)
        allowed, remaining, retry_after = _LIMITER.check(key=bucket_key, limit=limit, window_seconds=window_seconds)
        if not allowed:
            return JSONResponse(
                {
                    "detail": "Rate limit exceeded. Try again after the Retry-After seconds shown in the response headers.",
                    "bucket": bucket_name,
                    "limit": limit,
                    "window_seconds": window_seconds,
                    "retry_after_seconds": retry_after,
                },
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Window": str(window_seconds),
                },
            )

        response = await call_next(request)
        response.headers.setdefault("X-RateLimit-Limit", str(limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(remaining))
        response.headers.setdefault("X-RateLimit-Window", str(window_seconds))
        return response
