"""Result caching helpers backed by Redis."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

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


class JobCache:
    """Cache for job metadata stored as JSON payloads."""

    def __init__(self, redis: Redis, ttl_seconds: int, namespace: str = "jobs") -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._namespace = namespace

    async def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        raw = await self._redis.get(self._format_key(job_id))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    async def set(self, job_id: str, payload: Dict[str, Any]) -> None:
        serialized = json.dumps(payload)
        redis_key = self._format_key(job_id)
        if self._ttl > 0:
            await self._redis.set(redis_key, serialized, ex=self._ttl)
        else:
            await self._redis.set(redis_key, serialized)

    async def delete(self, job_id: str) -> None:
        await self._redis.delete(self._format_key(job_id))

    def _format_key(self, job_id: str) -> str:
        return f"{self._namespace}:{job_id}"

class SymbolicResultCache:
    """Cache for symbolic results to short-circuit repeat requests."""

    def __init__(self, redis: Redis, ttl_seconds: int, namespace: str = "symbolic") -> None:
        self._redis = redis
        self._ttl = ttl_seconds
        self._namespace = namespace

    async def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        raw = await self._redis.get(self._format_key(cache_key))
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    async def set(self, cache_key: str, payload: Dict[str, Any]) -> None:
        serialized = json.dumps(payload)
        key = self._format_key(cache_key)
        if self._ttl > 0:
            await self._redis.set(key, serialized, ex=self._ttl)
        else:
            await self._redis.set(key, serialized)

    async def delete(self, cache_key: str) -> None:
        await self._redis.delete(self._format_key(cache_key))

    def _format_key(self, cache_key: str) -> str:
        return f"{self._namespace}:{cache_key}"
