"""Redis-backed caching for symbolic evaluations."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, Optional

import redis

_DEFAULT_URL = "redis://redis:6379/0"
_TTL_SECONDS = 300

_redis_client: redis.Redis | None = None


def _get_client() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = os.getenv("REDIS_URL", _DEFAULT_URL)
        _redis_client = redis.Redis.from_url(url, decode_responses=True)
    return _redis_client


def build_cache_key(expr: str, subs: Optional[Dict[str, float]]) -> str:
    payload = {"expr": expr, "subs": subs or {}}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def get(expr: str, subs: Optional[Dict[str, float]]) -> Optional[Dict[str, object]]:
    client = _get_client()
    key = build_cache_key(expr, subs)
    raw = client.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        client.delete(key)
        return None


def set_result(expr: str, subs: Optional[Dict[str, float]], result: Dict[str, object]) -> None:
    client = _get_client()
    key = build_cache_key(expr, subs)
    client.setex(key, _TTL_SECONDS, json.dumps(result, separators=(",", ":")))
