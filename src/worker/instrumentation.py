"""Celery worker instrumentation helpers."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterable, Iterator, Mapping, Tuple, Type

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from src.gateway.instrumentation import job_id_short
from src.observability.metrics import JobMetrics, get_job_metrics

__all__ = [
    "get_worker_metrics",
    "worker_task_span",
    "compute_queue_wait_ms",
]


tracer = trace.get_tracer("worker.jobs")


def get_worker_metrics(namespace: str | None = None) -> JobMetrics:
    """Return metrics bundle for worker processes."""

    return get_job_metrics(namespace)


def compute_queue_wait_ms(headers: Mapping[str, str] | None) -> float | None:
    """Derive queue wait milliseconds from Celery headers."""

    if not headers:
        return None
    raw = headers.get("x-enqueued-at-ms")
    if raw is None:
        return None
    try:
        enqueued_ms = float(raw)
    except (TypeError, ValueError):
        return None
    now_ms = time.time() * 1000.0
    wait = max(0.0, now_ms - enqueued_ms)
    return wait


@contextmanager
def worker_task_span(
    job_id: str,
    queue: str,
    task: str,
    headers: Mapping[str, str] | None,
    metrics: JobMetrics,
    *,
    retry_exception_types: Iterable[Type[BaseException]] = (),
) -> Iterator[Span]:
    """Context manager capturing worker execution spans and metrics."""

    queue_wait_ms = compute_queue_wait_ms(headers)
    attributes = {
        "queue": queue,
        "task": task,
        "job_id": job_id_short(job_id),
    }
    if queue_wait_ms is not None:
        attributes["queue_wait_ms"] = queue_wait_ms
    start_time = time.perf_counter()
    outcome = "success"
    exception_types: Tuple[Type[BaseException], ...] = tuple(retry_exception_types)

    with tracer.start_as_current_span("jobs.execute", attributes=attributes) as span:
        for key, value in attributes.items():
            span.set_attribute(key, value)
        span.add_event("job.id", {"job_id": job_id})
        span.set_attribute("component", "worker")
        if queue_wait_ms is not None:
            metrics.job_wait_time_seconds.labels(queue=queue).observe(queue_wait_ms / 1000.0)
        try:
            yield span
        except exception_types as exc:  # type: ignore[arg-type]
            outcome = "retry"
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("outcome", outcome)
            raise
        except Exception as exc:  # noqa: BLE001
            outcome = "failed"
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("outcome", outcome)
            raise
        else:
            explicit_outcome = getattr(span, "attributes", {}).get("outcome")
            outcome = str(explicit_outcome) if explicit_outcome else "success"
            if not explicit_outcome:
                span.set_attribute("outcome", outcome)
            span.set_status(Status(StatusCode.OK) if outcome == "success" else Status(StatusCode.ERROR))
        finally:
            worker_process_ms = (time.perf_counter() - start_time) * 1000.0
            span.set_attribute("worker_process_ms", worker_process_ms)
            metrics.celery_task_runtime_seconds.labels(task=task).observe(worker_process_ms / 1000.0)
            metrics.jobs_in_progress.labels(queue=queue, task=task).dec()
            final_outcome = getattr(span, "attributes", {}).get("outcome", outcome)
            if final_outcome == "failed":
                metrics.jobs_failed.labels(queue=queue, task=task).inc()
