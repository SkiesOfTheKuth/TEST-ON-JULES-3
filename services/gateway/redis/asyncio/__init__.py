"""Very small subset of :mod:`redis.asyncio` required in tests."""

from __future__ import annotations

from typing import Any, Dict


class Redis:
    def __init__(self) -> None:
        self._store: Dict[str, Any] = {}

    @classmethod
    def from_url(cls, url: str, decode_responses: bool = True) -> "Redis":
        return cls()

    async def set(self, key: str, value: Any, ex: int | None = None) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def llen(self, key: str) -> int:
        value = self._store.get(key)
        if isinstance(value, list):
            return len(value)
        return 0

    async def close(self) -> None:
        return None


__all__ = ["Redis"]
