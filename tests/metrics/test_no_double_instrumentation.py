from __future__ import annotations

import importlib
import time

from prometheus_client import generate_latest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import InMemorySpanExporter, SimpleSpanProcessor

from src.observability.metrics import get_job_metrics


def _install_worker_tracing():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    worker_instr = importlib.reload(importlib.import_module("src.worker.instrumentation"))
    return exporter, worker_instr


def test_worker_span_singleton_metrics_and_tracing(monkeypatch):
    exporter, worker_instr = _install_worker_tracing()

    namespace = "no_double_instrumentation"
    metrics = get_job_metrics(namespace)

    job_id = "feed1234-dead-beef-cafe-123456789abc"
    queue = "calculator"
    task = "gateway.execute_job"
    headers = {"x-enqueued-at-ms": str(int(time.time() * 1000) - 25)}

    original_gauge_labels = metrics.jobs_in_progress.labels
    original_histogram_labels = metrics.celery_task_runtime_seconds.labels

    original_gauge_labels(queue=queue, task=task).set(0)
    original_histogram_labels(task=task)
    metrics.jobs_failed.labels(queue=queue, task=task)

    inc_calls = {"count": 0}
    dec_calls = {"count": 0}
    observe_calls = {"count": 0}

    class _GaugeProxy:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def inc(self, amount: float = 1.0) -> None:
            inc_calls["count"] += 1
            self._wrapped.inc(amount)

        def dec(self, amount: float = 1.0) -> None:
            dec_calls["count"] += 1
            self._wrapped.dec(amount)

        def __getattr__(self, item):
            return getattr(self._wrapped, item)

    class _HistogramProxy:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def observe(self, value: float) -> None:
            observe_calls["count"] += 1
            self._wrapped.observe(value)

        def __getattr__(self, item):
            return getattr(self._wrapped, item)

    def counting_gauge_labels(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _GaugeProxy(original_gauge_labels(*args, **kwargs))

    def counting_histogram_labels(*args, **kwargs):  # type: ignore[no-untyped-def]
        return _HistogramProxy(original_histogram_labels(*args, **kwargs))

    monkeypatch.setattr(metrics.jobs_in_progress, "labels", counting_gauge_labels)
    monkeypatch.setattr(metrics.celery_task_runtime_seconds, "labels", counting_histogram_labels)

    with worker_instr.worker_task_span(job_id, queue, task, headers, metrics) as outer_span:
        with worker_instr.worker_task_span(job_id, queue, task, headers, metrics) as inner_span:
            assert inner_span is outer_span
            time.sleep(0.002)

    spans = exporter.get_finished_spans()
    execute_spans = [span for span in spans if span.name == "jobs.execute"]
    assert len(execute_spans) == 1

    assert inc_calls["count"] == 1
    assert dec_calls["count"] == 1
    assert observe_calls["count"] == 1

    metrics_text = generate_latest().decode().splitlines()
    histogram_lines = [
        line
        for line in metrics_text
        if line.startswith(
            f"{namespace}_celery_task_runtime_seconds{{task=\"{task}\"}}"
        )
    ]
    assert len(histogram_lines) == 1

    gauge_lines = [
        line
        for line in metrics_text
        if line.startswith(
            f"{namespace}_jobs_in_progress{{queue=\"{queue}\",task=\"{task}\"}}"
        )
    ]
    assert gauge_lines == [
        f"{namespace}_jobs_in_progress{{queue=\"{queue}\",task=\"{task}\"}} 0.0"
    ]

    failed_lines = [
        line
        for line in metrics_text
        if line.startswith(
            f"{namespace}_jobs_failed{{queue=\"{queue}\",task=\"{task}\"}}"
        )
    ]
    assert failed_lines == [
        f"{namespace}_jobs_failed{{queue=\"{queue}\",task=\"{task}\"}} 0.0"
    ]

    assert metrics.jobs_in_progress._values[(queue, task)] == 0.0
    assert metrics.celery_task_runtime_seconds._values[(task,)] > 0.0
    assert metrics.jobs_failed._values[(queue, task)] == 0.0

    execute_span = execute_spans[0]
    assert execute_span.attributes["outcome"] == "success"
    assert isinstance(execute_span.attributes["worker_process_ms"], int)
    assert execute_span.attributes["worker_process_ms"] > 0
