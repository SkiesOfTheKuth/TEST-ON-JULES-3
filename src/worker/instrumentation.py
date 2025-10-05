"""Celery worker instrumentation helpers."""

from __future__ import annotations

import logging
import math
import time
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Callable, Iterable, Iterator, Mapping, Optional, Tuple, Type
from weakref import WeakKeyDictionary

from celery import Celery
_existing_signals = globals().get("signals")
try:  # pragma: no cover - optional Celery dependency
    from celery import signals  # type: ignore[attr-defined]
except ImportError:  # pragma: no cover - fallback for test doubles
    class _Signal:
        def __init__(self) -> None:
            self._receivers: list[tuple[Callable[..., None], Celery | None]] = []

        def connect(self, receiver: Callable[..., None] | None = None, *, sender: Celery | None = None, **_: Any):
            if receiver is None:

                def decorator(func: Callable[..., None]) -> Callable[..., None]:
                    self._receivers.append((func, sender))
                    return func

                return decorator

            self._receivers.append((receiver, sender))
            return receiver

        def send(self, sender: Celery | None = None, *args: Any, **kwargs: Any) -> None:
            for receiver, expected_sender in list(self._receivers):
                if expected_sender is not None and expected_sender is not sender:
                    continue
                receiver(sender, *args, **kwargs)

    class _SignalNamespace:
        def __init__(self) -> None:
            self.task_prerun = _Signal()
            self.task_postrun = _Signal()
            self.task_failure = _Signal()
            self.task_retry = _Signal()

    if _existing_signals and all(
        hasattr(_existing_signals, attr) for attr in ("task_prerun", "task_postrun", "task_failure", "task_retry")
    ):
        for attr in ("task_prerun", "task_postrun", "task_failure", "task_retry"):
            signal_obj = getattr(_existing_signals, attr, None)
            receivers = getattr(signal_obj, "_receivers", None)
            if isinstance(receivers, list):
                receivers.clear()
        signals = _existing_signals  # type: ignore[assignment]
    else:
        signals = _SignalNamespace()
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import Span, SpanContext, Status, StatusCode

from src.gateway.instrumentation import job_id_short
from src.observability.metrics import JobMetrics, get_job_metrics
from src.worker.metrics_app import create_app as _create_metrics_app

__all__ = [
    "get_worker_metrics",
    "setup_worker_signals",
    "create_worker_metrics_app",
    "worker_task_span",
    "compute_queue_wait_ms",
]


tracer = trace.get_tracer("worker.jobs")
logger = logging.getLogger(__name__)
_REQUEST_CTX_ATTR = "_observability_ctx"
_REQUEST_SPAN_ATTR = "_observability_span"
_INSTRUMENTED_WORKERS: "WeakKeyDictionary[Celery, bool]" = WeakKeyDictionary()
_METRICS_LABELS_ATTR = "_observability_metrics_labels"
_METRICS_START_ATTR = "_observability_metrics_start"
_METRICS_GAUGE_ATTR = "_observability_metrics_gauge_active"
_CLOCK_SKEW_LOGGED = False
_EXECUTE_DEPTH: ContextVar[int] = ContextVar("worker_jobs_execute_depth", default=0)


def get_worker_metrics(namespace: str | None = None) -> JobMetrics:
    """Return metrics bundle for worker processes."""

    return get_job_metrics(namespace)


def create_worker_metrics_app(*, path: str = "/metrics") -> FastAPI:
    """Return a lightweight FastAPI app that exposes worker metrics."""

    return _create_metrics_app(path=path)


def setup_worker_signals(
    app: Celery,
    *,
    namespace: str | None = None,
    retry_exception_types: Iterable[Type[BaseException]] = (),
) -> None:
    """Connect Celery signals to update tracing spans and Prometheus metrics."""

    if _INSTRUMENTED_WORKERS.get(app):
        return

    metrics = get_worker_metrics(namespace)
    exception_types: Tuple[Type[BaseException], ...] = tuple(retry_exception_types)

    def _resolve_queue(task) -> str:
        request = getattr(task, "request", None)
        if request is not None:
            delivery_info = getattr(request, "delivery_info", {}) or {}
            routing_key = delivery_info.get("routing_key")
            if routing_key:
                return str(routing_key)
            queue_name = delivery_info.get("queue")
            if queue_name:
                return str(queue_name)
        return getattr(task, "queue", "calculator")

    def _task_request(task):
        return getattr(task, "request", None)

    def _store_labels(request, queue: str, task_name: str) -> None:
        setattr(request, _METRICS_LABELS_ATTR, (queue, task_name))
        setattr(request, _METRICS_GAUGE_ATTR, True)

    def _labels_from_request(request) -> Tuple[str, str] | None:
        labels = getattr(request, _METRICS_LABELS_ATTR, None)
        if isinstance(labels, tuple) and len(labels) == 2:
            return str(labels[0]), str(labels[1])
        return None

    def _decrement_in_progress(request) -> Tuple[str, str] | None:
        labels = _labels_from_request(request)
        if labels and getattr(request, _METRICS_GAUGE_ATTR, False):
            queue, task_name = labels
            metrics.jobs_in_progress.labels(queue=queue, task=task_name).dec()
            setattr(request, _METRICS_GAUGE_ATTR, False)
        return labels

    @signals.task_prerun.connect(sender=app)  # pragma: no cover - Celery wiring
    def _task_prerun(sender, task_id, task, *_, **__):
        request = _task_request(task)
        if request is None:
            return
        queue = _resolve_queue(task)
        task_name = task.name
        metrics.jobs_in_progress.labels(queue=queue, task=task_name).inc()
        _store_labels(request, queue, task_name)
        setattr(request, _METRICS_START_ATTR, time.perf_counter())

        headers = getattr(request, "headers", None)
        queue_wait_ms = compute_queue_wait_ms(headers)
        if queue_wait_ms is not None:
            metrics.job_wait_time_seconds.labels(queue=queue).observe(queue_wait_ms / 1000.0)

        context = worker_task_span(
            job_id=task_id,
            queue=queue,
            task=task_name,
            headers=headers,
            metrics=metrics,
            retry_exception_types=exception_types,
            manage_metrics=False,
        )
        span = context.__enter__()
        setattr(request, _REQUEST_CTX_ATTR, context)
        setattr(request, _REQUEST_SPAN_ATTR, span)

    @signals.task_failure.connect(sender=app)  # pragma: no cover - Celery wiring
    def _task_failure(sender, task_id, exception, traceback, einfo, task, **kwargs):
        request = _task_request(task)
        if request is None:
            return
        span = getattr(request, _REQUEST_SPAN_ATTR, None)
        if span is not None:
            try:
                span.record_exception(exception)
            except Exception:  # pragma: no cover - defensive
                pass
            span.set_status(Status(StatusCode.ERROR))
            span.set_attribute("outcome", "failed")
            span.add_event(
                "job.failed",
                {"exception.type": type(exception).__name__ if exception else "Unknown"},
            )

        labels = _decrement_in_progress(request)
        if labels is None:
            labels = (_resolve_queue(task), task.name)
        metrics.jobs_failed.labels(queue=labels[0], task=labels[1]).inc()

    @signals.task_retry.connect(sender=app)  # pragma: no cover - Celery wiring
    def _task_retry(sender, request, reason, einfo, **kwargs):
        span = getattr(request, _REQUEST_SPAN_ATTR, None)
        if span is None:
            return
        if reason is not None:
            try:
                span.record_exception(reason)
            except Exception:  # pragma: no cover - defensive
                pass
        span.set_attribute("outcome", "retry")
        span.set_status(Status(StatusCode.ERROR))
        span.add_event(
            "job.retry",
            {"exception.type": type(reason).__name__ if reason else "Unknown"},
        )
        _decrement_in_progress(request)

    @signals.task_postrun.connect(sender=app)  # pragma: no cover - Celery wiring
    def _task_postrun(sender, task_id, task, retval, state, **kwargs):
        request = _task_request(task)
        if request is None:
            return
        context = getattr(request, _REQUEST_CTX_ATTR, None)
        span = getattr(request, _REQUEST_SPAN_ATTR, None)

        if span is not None and state:
            outcome = str(state).upper()
            if outcome == "RETRY":
                span.set_attribute("outcome", "retry")
            elif outcome == "FAILURE":
                span.set_attribute("outcome", "failed")

        labels = _decrement_in_progress(request)
        if labels is None:
            labels = (_resolve_queue(task), task.name)

        start_time = getattr(request, _METRICS_START_ATTR, None)
        if isinstance(start_time, float):
            runtime = max(0.0, time.perf_counter() - start_time)
            metrics.celery_task_runtime_seconds.labels(task=labels[1]).observe(runtime)

        if context is not None:
            context.__exit__(None, None, None)

        for attr in (
            _REQUEST_CTX_ATTR,
            _REQUEST_SPAN_ATTR,
            _METRICS_LABELS_ATTR,
            _METRICS_START_ATTR,
            _METRICS_GAUGE_ATTR,
        ):
            if hasattr(request, attr):
                delattr(request, attr)

    _INSTRUMENTED_WORKERS[app] = True


def compute_queue_wait_ms(headers: Mapping[str, str] | None) -> int | None:
    """Derive queue wait milliseconds from Celery headers."""

    if not headers:
        return None
    raw = headers.get("x-enqueued-at-ms")
    if raw is None:
        return None
    try:
        enqueued_ms = int(float(raw))
    except (TypeError, ValueError):
        return None
    now_ms = int(time.time() * 1000)
    wait = now_ms - enqueued_ms
    if wait < 0:
        global _CLOCK_SKEW_LOGGED
        if not _CLOCK_SKEW_LOGGED:
            logger.debug(
                "Detected negative queue wait due to clock skew; clamping to zero."
            )
            _CLOCK_SKEW_LOGGED = True
        wait = 0
    return int(wait)


@contextmanager
def worker_task_span(
    job_id: str,
    queue: str,
    task: str,
    headers: Mapping[str, str] | None,
    metrics: Optional[JobMetrics],
    *,
    retry_exception_types: Iterable[Type[BaseException]] = (),
    manage_metrics: bool = True,
) -> Iterator[Span]:
    """Context manager capturing worker execution spans and metrics."""

    depth = _EXECUTE_DEPTH.get()
    if depth > 0:
        token = _EXECUTE_DEPTH.set(depth + 1)
        try:
            yield trace.get_current_span()
        finally:
            _EXECUTE_DEPTH.reset(token)
        return

    token = _EXECUTE_DEPTH.set(1)
    try:
        queue_wait_ms = compute_queue_wait_ms(headers)
        attributes = {
            "queue": queue,
            "task": task,
            "job_id_short": job_id_short(job_id),
        }
        if queue_wait_ms is not None:
            attributes["queue_wait_ms"] = queue_wait_ms

        exception_types: Tuple[Type[BaseException], ...] = tuple(retry_exception_types)
        start_time = time.perf_counter()
        outcome = "success"

        parent_context: SpanContext | None = None
        if headers:
            extracted = extract(dict(headers))
            if isinstance(extracted, SpanContext) and extracted.is_valid:
                parent_context = extracted

        metrics_enabled = manage_metrics and metrics is not None
        if metrics_enabled:
            metrics.jobs_in_progress.labels(queue=queue, task=task).inc()

        with tracer.start_as_current_span(
            "jobs.execute",
            attributes=attributes,
            parent=parent_context,
        ) as span:
            for key, value in attributes.items():
                span.set_attribute(key, value)
            if metrics_enabled and queue_wait_ms is not None:
                metrics.job_wait_time_seconds.labels(queue=queue).observe(queue_wait_ms / 1000.0)
            try:
                yield span
            except exception_types as exc:  # type: ignore[arg-type]
                outcome = "retry"
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("outcome", outcome)
                span.add_event(
                    "job.retry",
                    {
                        "error.type": type(exc).__name__,
                        "error.message": str(exc),
                    },
                )
                raise
            except Exception as exc:  # noqa: BLE001
                outcome = "failed"
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                span.set_attribute("outcome", outcome)
                span.add_event(
                    "job.failed",
                    {
                        "error.type": type(exc).__name__,
                        "error.message": str(exc),
                    },
                )
                raise
            else:
                explicit_outcome = getattr(span, "attributes", {}).get("outcome")
                outcome = str(explicit_outcome) if explicit_outcome else "success"
                if not explicit_outcome:
                    span.set_attribute("outcome", outcome)
                span.set_status(
                    Status(StatusCode.OK) if outcome == "success" else Status(StatusCode.ERROR)
                )
            finally:
                elapsed_ms = max(0.0, (time.perf_counter() - start_time) * 1000.0)
                worker_process_ms = max(0, int(math.ceil(elapsed_ms)))
                span.set_attribute("worker_process_ms", worker_process_ms)
                if metrics_enabled:
                    metrics.celery_task_runtime_seconds.labels(task=task).observe(
                        worker_process_ms / 1000.0
                    )
                    metrics.jobs_in_progress.labels(queue=queue, task=task).dec()
                    final_outcome = getattr(span, "attributes", {}).get("outcome", outcome)
                    if final_outcome == "failed":
                        metrics.jobs_failed.labels(queue=queue, task=task).inc()
    finally:
        _EXECUTE_DEPTH.reset(token)
