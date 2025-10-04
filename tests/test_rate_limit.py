from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

import pytest


def _install_redis_stub() -> None:
    parent = sys.modules.setdefault("redis", types.ModuleType("redis"))
    module = types.ModuleType("redis.asyncio")
    parent.asyncio = module  # type: ignore[attr-defined]

    class _RedisStub:  # noqa: D401 - simple stand-in used in tests
        pass

    module.Redis = _RedisStub  # type: ignore[attr-defined]
    sys.modules["redis.asyncio"] = module


_install_redis_stub()


def _load_rate_limit_module():
    module_path = Path(__file__).resolve().parents[1] / "services/gateway/app/rate_limit.py"
    spec = importlib.util.spec_from_file_location("calculator_gateway_rate_limit", module_path)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive guard
        raise RuntimeError("Unable to load rate_limit module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


rate_limit = _load_rate_limit_module()
RateLimiter = rate_limit.RateLimiter


class DummyRedis:
    """Minimal Redis stub that exercises the Lua contract used by the limiter."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[tuple[int, str]]] = {}

    async def eval(
        self,
        script: str,
        numkeys: int,
        key: str,
        now_ms: int,
        window_ms: int,
        limit: int,
        ttl_ms: int,
        member: str,
    ) -> int:
        assert "ARGV[5]" in script, "unique member argument must be consumed by the Lua script"
        bucket = [entry for entry in self._buckets.get(key, []) if entry[0] > now_ms - window_ms]
        if len(bucket) >= limit:
            self._buckets[key] = bucket
            return 0
        bucket.append((now_ms, member))
        self._buckets[key] = bucket
        return 1


def test_rate_limiter_enforces_burst_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    redis = DummyRedis()
    limiter = RateLimiter(redis, limit=2, window_seconds=1, namespace="test")

    monkeypatch.setattr(rate_limit.time, "time", lambda: 12345.0)

    async def _run() -> None:
        assert await limiter.allow("client")
        assert await limiter.allow("client")
        assert not await limiter.allow("client")

    asyncio.run(_run())
