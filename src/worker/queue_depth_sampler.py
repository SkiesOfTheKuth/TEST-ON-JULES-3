"""Utility for sampling queue depth and updating Prometheus gauges."""

from __future__ import annotations

import asyncio
import threading
from typing import Sequence

try:
    from redis import Redis  # type: ignore[assignment]
except ImportError:  # pragma: no cover - fallback for stubbed redis package
    from redis.asyncio import Redis as AsyncRedis

    class Redis:  # type: ignore[override]
        """Synchronous facade over the asyncio Redis client."""

        @classmethod
        def from_url(cls, url: str):  # type: ignore[override]
            return _AsyncRedisWrapper(AsyncRedis.from_url(url))


    class _AsyncRedisWrapper:
        def __init__(self, client: AsyncRedis) -> None:
            self._client = client

        def llen(self, key: str) -> int:
            return int(asyncio.run(self._client.llen(key)))

        def close(self) -> None:
            asyncio.run(self._client.close())

from src.observability.metrics import JobMetrics

__all__ = ["QueueDepthSampler"]


class QueueDepthSampler:
    """Background sampler that periodically updates queue depth gauges."""

    def __init__(
        self,
        redis_url: str,
        queue_names: Sequence[str],
        metrics: JobMetrics,
        *,
        interval_seconds: float = 5.0,
    ) -> None:
        self._redis_url = redis_url
        self._queue_names = list(queue_names)
        self._metrics = metrics
        self._interval = max(interval_seconds, 0.5)
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="queue-depth", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        client = Redis.from_url(self._redis_url)
        try:
            while not self._stop.is_set():
                self._sample_once(client)
                self._stop.wait(self._interval)
        finally:
            try:
                client.close()
            except Exception:  # pragma: no cover - defensive cleanup
                pass

    def _sample_once(self, client: Redis) -> None:
        for queue in self._queue_names:
            try:
                depth = 0
                for candidate in (f"queue:{queue}", queue, f"{queue}-applied"):
                    try:
                        value = client.llen(candidate)
                    except Exception:
                        continue
                    if value:
                        depth = int(value)
                        break
            except Exception:
                continue
            self._metrics.queue_depth.labels(queue=queue).set(float(depth))

    def add_queue(self, queue: str) -> None:
        if queue not in self._queue_names:
            self._queue_names.append(queue)
