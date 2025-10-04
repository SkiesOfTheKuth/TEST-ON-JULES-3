"""Result caching helpers backed by Redis."""

from __future__ import annotations

import json
from typing import Optional

from redis.asyncio import Redis


class ResultCache:
    def __init__(self, redis: Redis, ttl_seconds: int, namespace: str = "cache") -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._namespace = namespace

    async def get(self, key: str) -> Optional[float]:
        raw = await self._redis.get(self._format_key(key))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            return float(payload["value"])
        except (KeyError, ValueError, TypeError):
            return None

    async def set(self, key: str, value: float) -> None:
        payload = json.dumps({"value": value})
        redis_key = self._format_key(key)
        if self._ttl > 0:
            await self._redis.set(redis_key, payload, ex=self._ttl)
        else:
            await self._redis.set(redis_key, payload)

    def _format_key(self, key: str) -> str:
        return f"{self._namespace}:{key}"
