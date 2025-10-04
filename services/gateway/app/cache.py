"""Result caching helpers backed by Redis."""

from __future__ import annotations

import json
from typing import Optional

from redis.asyncio import Redis


class ResultCache:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self._redis = redis
        self._ttl = ttl_seconds

    async def get(self, key: str) -> Optional[float]:
        raw = await self._redis.get(f"cache:{key}")
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            return float(payload["value"])
        except (KeyError, ValueError, TypeError):
            return None

    async def set(self, key: str, value: float) -> None:
        payload = json.dumps({"value": value})
        await self._redis.set(f"cache:{key}", payload, ex=self._ttl)
