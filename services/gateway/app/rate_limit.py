"""Redis-backed rate limiting utilities."""

from __future__ import annotations

import time

from redis.asyncio import Redis


class RateLimiter:
    def __init__(self, redis: Redis, limit: int, window_seconds: int, namespace: str) -> None:
        self._redis = redis
        self._limit = limit
        self._window = window_seconds
        self._namespace = namespace

    async def allow(self, key: str) -> bool:
        now = int(time.time())
        window_key = f"{self._namespace}:{key}:{now // self._window}"
        count = await self._redis.incr(window_key)
        if count == 1:
            await self._redis.expire(window_key, self._window)
        return count <= self._limit
