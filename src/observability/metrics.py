"""Prometheus metrics shared across gateway and worker services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from prometheus_client import Counter, Gauge, Histogram, REGISTRY

__all__ = ["JobMetrics", "get_job_metrics"]


@dataclass(frozen=True)
class JobMetrics:
    """Bundle of Prometheus collectors for job processing."""

    jobs_enqueued_total: Counter
    jobs_failed: Counter
    jobs_in_progress: Gauge
    queue_depth: Gauge
    celery_task_runtime_seconds: Histogram
    job_wait_time_seconds: Histogram


_METRICS_BY_NAMESPACE: Dict[Tuple[Optional[str]], JobMetrics] = {}


def _get_or_register(metric_cls, name: str, documentation: str, *, labelnames=(), namespace: str | None = None, **kwargs):
    """Return an existing collector or create a new one safely."""

    full_name = f"{namespace}_{name}" if namespace else name
    try:
        return metric_cls(
            name,
            documentation,
            labelnames=labelnames,
            namespace=namespace,
            **kwargs,
        )
    except ValueError:
        existing = REGISTRY._names_to_collectors.get(full_name)  # type: ignore[attr-defined]
        if existing is None:
            raise
        return existing


def _runtime_buckets() -> Tuple[float, ...]:
    buckets = [0.01]
    current = 0.01
    while current < 120:
        current *= 2
        if current > 120:
            break
        buckets.append(round(current, 4))
    if buckets[-1] != 120.0:
        buckets.append(120.0)
    return tuple(buckets)


def get_job_metrics(namespace: str | None = None) -> JobMetrics:
    """Return lazily-instantiated metrics with optional namespace."""

    key = (namespace,)
    metrics = _METRICS_BY_NAMESPACE.get(key)
    if metrics is not None:
        return metrics

    runtime_buckets = _runtime_buckets()

    metrics = JobMetrics(
        jobs_enqueued_total=_get_or_register(
            Counter,
            "jobs_enqueued_total",
            "Total number of asynchronous jobs submitted to the calculator queues.",
            labelnames=("queue",),
            namespace=namespace,
        ),
        jobs_failed=_get_or_register(
            Counter,
            "jobs_failed",
            "Count of jobs that failed permanently after worker execution attempts.",
            labelnames=("queue", "task"),
            namespace=namespace,
        ),
        jobs_in_progress=_get_or_register(
            Gauge,
            "jobs_in_progress",
            "Jobs currently being processed by workers.",
            labelnames=("queue", "task"),
            namespace=namespace,
        ),
        queue_depth=_get_or_register(
            Gauge,
            "queue_depth",
            "Depth of the Celery queue sampled from Redis.",
            labelnames=("queue",),
            namespace=namespace,
        ),
        celery_task_runtime_seconds=_get_or_register(
            Histogram,
            "celery_task_runtime_seconds",
            "Histogram of Celery task runtime durations.",
            labelnames=("task",),
            namespace=namespace,
            buckets=runtime_buckets,
        ),
        job_wait_time_seconds=_get_or_register(
            Histogram,
            "job_wait_time_seconds",
            "Histogram of queue wait times from enqueue to worker start.",
            labelnames=("queue",),
            namespace=namespace,
            buckets=runtime_buckets,
        ),
    )

    _METRICS_BY_NAMESPACE[key] = metrics
    return metrics
