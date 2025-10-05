"""In-memory Redis asyncio stub for offline testing."""

from __future__ import annotations

import asyncio
from typing import Dict, Optional


class _PubSub:
    def __init__(self, redis: "Redis") -> None:
        self._redis = redis
        self._channels: set[str] = set()
        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed = False
        redis._pubsubs.add(self)

    async def subscribe(self, *channels: str) -> None:
        self._channels.update(channels)

    async def unsubscribe(self, *channels: str) -> None:
        for channel in channels or []:
            self._channels.discard(channel)

    async def listen(self):
        while not self._closed:
            message = await self._queue.get()
            if message is None:
                break
            yield message

    async def dispatch(self, channel: str, message: str) -> int:
        if self._closed or channel not in self._channels:
            return 0
        await self._queue.put({"type": "message", "channel": channel, "data": message})
        return 1

    async def close(self) -> None:
        if not self._closed:
            self._closed = True
            await self._queue.put(None)
            self._redis._pubsubs.discard(self)


class Redis:
    def __init__(self) -> None:
        self._storage: Dict[str, str] = {}
        self._pubsubs: set[_PubSub] = set()

    @classmethod
    def from_url(cls, url: str, decode_responses: bool = True) -> "Redis":  # noqa: D401 - parity
        return cls()

    async def get(self, key: str) -> Optional[str]:
        return self._storage.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:  # noqa: ARG002 - TTL ignored
        self._storage[key] = value

    async def delete(self, key: str) -> None:
        self._storage.pop(key, None)

    async def llen(self, key: str) -> int:
        return 0

    async def publish(self, channel: str, message: str) -> int:
        delivered = 0
        for subscriber in list(self._pubsubs):
            delivered += await subscriber.dispatch(channel, message)
        return delivered

    def pubsub(self) -> _PubSub:
        return _PubSub(self)

    async def close(self) -> None:
        while self._pubsubs:
            subscriber = self._pubsubs.pop()
            await subscriber.close()


__all__ = ["Redis"]
