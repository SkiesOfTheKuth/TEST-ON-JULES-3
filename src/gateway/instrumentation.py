"""Gateway instrumentation helpers for async job flows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Dict, Iterator

from opentelemetry import trace
from opentelemetry.trace import Span

from src.observability.metrics import JobMetrics, get_job_metrics

__all__ = [
    "job_id_short",
    "get_job_metrics",
    "get_gateway_metrics",
    "start_enqueue_span",
    "start_job_status_span",
    "start_ws_span",
    "prepare_enqueue_headers",
    "record_enqueue_success",
]


tracer = trace.get_tracer("gateway.jobs")


def job_id_short(job_id: str) -> str:
    """Return a low-cardinality identifier for span attributes."""

    compact = job_id.replace("-", "")
    return compact[:8]


def get_gateway_metrics(namespace: str | None = None) -> JobMetrics:
    """Expose job metrics with the configured namespace."""

    return get_job_metrics(namespace)


@contextmanager
def start_enqueue_span(job_id: str, queue: str, task: str) -> Iterator[Span]:
    """Start a span describing the enqueue lifecycle."""

    attributes = {"queue": queue, "task": task, "job_id": job_id_short(job_id)}
    with tracer.start_as_current_span("jobs.enqueue", attributes=attributes) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        span.add_event("job.id", {"job_id": job_id})
        span.set_attribute("component", "gateway")
        yield span


@contextmanager
def start_job_status_span(job_id: str, queue: str | None = None) -> Iterator[Span]:
    """Span for polling job status."""

    attributes = {"job_id": job_id_short(job_id)}
    if queue:
        attributes["queue"] = queue
    with tracer.start_as_current_span("jobs.status", attributes=attributes) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        span.add_event("job.id", {"job_id": job_id})
        span.set_attribute("component", "gateway")
        yield span


@contextmanager
def start_ws_span(stage: str, job_id: str, queue: str | None = None) -> Iterator[Span]:
    """Span helper for WebSocket stages (connect/hydrate/stream)."""

    attributes = {"stage": stage, "job_id": job_id_short(job_id)}
    if queue:
        attributes["queue"] = queue
    with tracer.start_as_current_span("jobs.ws", attributes=attributes) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        span.add_event("job.id", {"job_id": job_id})
        span.set_attribute("component", "gateway")
        span.set_attribute("ws.stage", stage)
        yield span


def prepare_enqueue_headers(
    metrics: JobMetrics,
    queue: str,
    task: str,
) -> Dict[str, str]:
    """Increment gauges ahead of enqueue and return Celery headers."""

    metrics.jobs_in_progress.labels(queue=queue, task=task).inc()
    enqueued_ms = int(time.time() * 1000)
    return {"x-enqueued-at-ms": str(enqueued_ms)}


def record_enqueue_success(metrics: JobMetrics, queue: str) -> None:
    """Record a successful enqueue operation."""

    metrics.jobs_enqueued_total.labels(queue=queue).inc()
