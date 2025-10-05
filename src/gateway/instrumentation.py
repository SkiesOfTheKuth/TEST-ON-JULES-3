"""Gateway instrumentation helpers for async job flows."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Dict, Iterator, MutableMapping

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.trace import Span, SpanContext

from src.observability.metrics import JobMetrics, get_job_metrics
from src.observability.prom_installer import install_prometheus_endpoint

__all__ = [
    "job_id_short",
    "get_job_metrics",
    "get_gateway_metrics",
    "expose_gateway_metrics",
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


def expose_gateway_metrics(app: FastAPI, *, path: str = "/metrics") -> None:
    """Ensure the FastAPI gateway exposes a Prometheus metrics endpoint."""

    install_prometheus_endpoint(app, path=path)


@contextmanager
def start_enqueue_span(job_id: str, queue: str, task: str) -> Iterator[Span]:
    """Start a span describing the enqueue lifecycle."""

    attributes = {
        "queue": queue,
        "task": task,
        "job_id_short": job_id_short(job_id),
    }
    with tracer.start_as_current_span("jobs.enqueue", attributes=attributes) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        yield span


@contextmanager
def start_job_status_span(job_id: str, queue: str | None = None) -> Iterator[Span]:
    """Span for polling job status."""

    attributes = {"job_id_short": job_id_short(job_id)}
    if queue:
        attributes["queue"] = queue
    with tracer.start_as_current_span("jobs.poll", attributes=attributes) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        yield span


@contextmanager
def start_ws_span(
    stage: str,
    job_id: str,
    queue: str | None = None,
    *,
    link_from: Span | SpanContext | None = None,
) -> Iterator[Span]:
    """Span helper for WebSocket stages (connect/hydrate/stream)."""

    allowed_stages = {"connect", "hydrate", "stream"}
    if stage not in allowed_stages:
        raise ValueError(f"Unsupported WebSocket stage '{stage}'")

    attributes = {"job_id_short": job_id_short(job_id)}
    span_name = f"ws.{stage}"
    links: list[SpanContext] = []
    enqueue_context = _extract_span_context(link_from)
    if enqueue_context is not None:
        links.append(enqueue_context)
    with tracer.start_as_current_span(span_name, attributes=attributes, links=links) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        yield span


def _extract_span_context(span_or_context: Span | SpanContext | None) -> SpanContext | None:
    if isinstance(span_or_context, Span):
        return span_or_context.get_span_context()
    if isinstance(span_or_context, SpanContext):
        return span_or_context
    return None


def prepare_enqueue_headers(
    metrics: JobMetrics,
    queue: str,
    task: str,
    *,
    headers: MutableMapping[str, str] | None = None,
) -> Dict[str, str]:
    """Return Celery headers used for downstream queue wait calculations."""

    carrier: MutableMapping[str, str] = headers if headers is not None else {}
    enqueued_ms = int(time.time() * 1000)
    carrier["x-enqueued-at-ms"] = str(enqueued_ms)
    inject(carrier)
    return dict(carrier)


def record_enqueue_success(metrics: JobMetrics, queue: str) -> None:
    """Record a successful enqueue operation."""

    metrics.jobs_enqueued_total.labels(queue=queue).inc()
