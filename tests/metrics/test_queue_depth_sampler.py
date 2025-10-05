from __future__ import annotations

from typing import Dict

from src.observability.metrics import get_job_metrics
from src.worker.queue_depth_sampler import QueueDepthSampler


class _StubRedis:
    def __init__(self, lengths: Dict[str, int]) -> None:
        self.lengths = lengths

    def llen(self, key: str) -> int:
        return self.lengths.get(key, 0)

    def close(self) -> None:  # pragma: no cover - compatibility
        pass


def _get_gauge_value(metric, **labels) -> float:
    sample = next(
        sample
        for collector in metric.collect()
        for sample in collector.samples
        if all(sample.labels.get(k) == v for k, v in labels.items())
    )
    return sample.value


def test_queue_depth_sampler_updates_gauge() -> None:
    metrics = get_job_metrics(None)
    sampler = QueueDepthSampler("redis://test", ["calculator"], metrics, interval_seconds=0.5)
    client = _StubRedis({"calculator": 7})

    sampler._sample_once(client)  # type: ignore[attr-defined]

    assert _get_gauge_value(metrics.queue_depth, queue="calculator") == 7.0

    client.lengths["calculator"] = 2
    sampler._sample_once(client)  # type: ignore[attr-defined]

    assert _get_gauge_value(metrics.queue_depth, queue="calculator") == 2.0
