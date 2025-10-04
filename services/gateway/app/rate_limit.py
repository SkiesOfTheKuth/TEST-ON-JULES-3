"""Redis-backed rate limiting utilities."""

from __future__ import annotations

import time
from typing import Final

from redis.asyncio import Redis


class RateLimiter:
    """Sliding window rate limiter backed by Redis sorted sets."""

    _LUA_SCRIPT: Final[str] = """
        local key = KEYS[1]
        local now = tonumber(ARGV[1])
        local window = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])

        redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
        local current = redis.call('ZCARD', key)
        if current >= limit then
            return 0
        end

        redis.call('ZADD', key, now, now)
        redis.call('PEXPIRE', key, window)
        return 1
    """

    def __init__(self, redis: Redis, limit: int, window_seconds: int, namespace: str) -> None:
        self._redis = redis
        self._limit = limit
        self._window = window_seconds
        self._namespace = namespace

    async def allow(self, key: str) -> bool:
        if self._limit <= 0:
            return True
        now_ms = int(time.time() * 1000)
        redis_key = f"{self._namespace}:{key}"
        result = await self._redis.eval(
            self._LUA_SCRIPT,
            1,
            redis_key,
            now_ms,
            self._window * 1000,
            self._limit,
        )
        return bool(result)
