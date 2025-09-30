"""Simple in-process rate limiting for the calculator service."""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, DefaultDict, Tuple


_LIMIT_PATTERN = re.compile(r"^(?P<count>\d+)\s*(?:/|\s+per\s+)(?P<unit>second|minute|hour)s?$", re.IGNORECASE)


class RateLimitParseError(ValueError):
    """Raised when the rate limit configuration string is invalid."""


@dataclass(slots=True)
class RateLimit:
    count: int
    window_seconds: float


class SimpleRateLimiter:
    """Thread-safe fixed-window rate limiter."""

    def __init__(self, limit_provider: Callable[[], str | None]):
        self._limit_provider = limit_provider
        self._lock = threading.Lock()
        self._buckets: DefaultDict[str, Deque[float]] = defaultdict(deque)
        self._cached_limit: RateLimit | None = None
        self._cached_token: str | None = None

    def _parse_limit(self, raw: str | None) -> RateLimit | None:
        if not raw:
            return None

        raw = raw.strip()
        if raw.lower() in {"none", "unlimited", "off"}:
            return None

        match = _LIMIT_PATTERN.match(raw)
        if not match:
            raise RateLimitParseError(
                "RATE_LIMIT must follow '<count>/<unit>' (e.g., '60/minute')."
            )

        count = int(match.group("count"))
        unit = match.group("unit").lower()
        window_seconds = {"second": 1.0, "minute": 60.0, "hour": 3600.0}[unit]
        return RateLimit(count=count, window_seconds=window_seconds)

    def _current_limit(self) -> RateLimit | None:
        token = self._limit_provider()
        if token == self._cached_token:
            return self._cached_limit

        limit = self._parse_limit(token)
        self._cached_token = token
        self._cached_limit = limit
        return limit

    def allow_request(self, key: str) -> Tuple[bool, float | None]:
        now = time.monotonic()
        with self._lock:
            limit = self._current_limit()
            if limit is None or limit.count <= 0:
                return True, None

            bucket = self._buckets[key]
            window_start = now - limit.window_seconds

            while bucket and bucket[0] <= window_start:
                bucket.popleft()

            if len(bucket) >= limit.count:
                retry_after = limit.window_seconds - (now - bucket[0])
                return False, max(retry_after, 0.0)

            bucket.append(now)
            return True, None


class RateLimitExceeded(Exception):
    """Raised when a request exceeds the configured rate limit."""

    def __init__(self, retry_after: float | None):
        super().__init__("Rate limit exceeded")
        self.retry_after = retry_after


def rate_limited(view):
    """Decorator enforcing the global rate limit for the calculator API."""

    from functools import wraps
    from flask import current_app, request

    @wraps(view)
    def wrapper(*args, **kwargs):
        limiter: SimpleRateLimiter = current_app.extensions["calculator_rate_limiter"]
        remote_addr = request.remote_addr or "unknown"
        allowed, retry_after = limiter.allow_request(remote_addr)
        if not allowed:
            raise RateLimitExceeded(retry_after)
        return view(*args, **kwargs)

    return wrapper


__all__ = ["SimpleRateLimiter", "RateLimitExceeded", "rate_limited"]
