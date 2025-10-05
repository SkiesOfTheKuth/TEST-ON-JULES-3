from __future__ import annotations

import importlib
import os
import re
import sys
import time
from collections import Counter
from typing import Iterable, Mapping

import pytest

trace = None
extract = None
TracerProvider = None
InMemorySpanExporter = None
SimpleSpanProcessor = None
SpanContext = None
StatusCode = None
get_job_metrics = None


def _restore_otel_modules() -> None:
    """Ensure our in-repo OpenTelemetry shims replace any test stubs."""

    otel_modules = [
        "opentelemetry",
        "opentelemetry.trace",
        "opentelemetry.propagate",
        "opentelemetry.exporter.otlp.proto.http.trace_exporter",
        "opentelemetry.sdk.trace",
        "opentelemetry.sdk.trace.export",
        "opentelemetry.sdk.resources",
        "prometheus_client",
    ]
    removed = False
    for name in otel_modules:
        module = sys.modules.get(name)
        if module is not None and not getattr(module, "__file__", None):
            sys.modules.pop(name, None)
            removed = True
    if removed:
        importlib.invalidate_caches()
    trace_module = importlib.import_module("opentelemetry.trace")
    propagate_module = importlib.import_module("opentelemetry.propagate")
    sdk_trace_module = importlib.import_module("opentelemetry.sdk.trace")
    sdk_export_module = importlib.import_module("opentelemetry.sdk.trace.export")
    importlib.import_module("opentelemetry.sdk.resources")
    importlib.import_module("prometheus_client")
    metrics_module = importlib.import_module("src.observability.metrics")

    globals().update(
        trace=trace_module,
        extract=propagate_module.extract,
        TracerProvider=sdk_trace_module.TracerProvider,
        InMemorySpanExporter=sdk_export_module.InMemorySpanExporter,
        SimpleSpanProcessor=sdk_export_module.SimpleSpanProcessor,
        SpanContext=trace_module.SpanContext,
        StatusCode=trace_module.StatusCode,
        get_job_metrics=metrics_module.get_job_metrics,
    )


_restore_otel_modules()


def _install_tracing() -> tuple[InMemorySpanExporter, object, object]:
    _restore_otel_modules()
    prev_sampler = os.environ.get("OTEL_TRACES_SAMPLER")
    prev_arg = os.environ.get("OTEL_TRACES_SAMPLER_ARG")
    if prev_sampler is None:
        os.environ["OTEL_TRACES_SAMPLER"] = "parentbased_always_on"
    if prev_arg is None:
        os.environ.pop("OTEL_TRACES_SAMPLER_ARG", None)
    trace_module = importlib.import_module("opentelemetry.trace")
    sdk_trace_module = importlib.import_module("opentelemetry.sdk.trace")
    sdk_export_module = importlib.import_module("opentelemetry.sdk.trace.export")
    exporter = sdk_export_module.InMemorySpanExporter()
    provider = sdk_trace_module.TracerProvider()
    provider.add_span_processor(sdk_export_module.SimpleSpanProcessor(exporter))
    trace_module.set_tracer_provider(provider)
    globals()["trace"] = trace_module

    gateway_instrumentation = importlib.reload(importlib.import_module("src.gateway.instrumentation"))
    worker_instrumentation = importlib.reload(importlib.import_module("src.worker.instrumentation"))

    if prev_sampler is None:
        os.environ.pop("OTEL_TRACES_SAMPLER", None)
    else:
        os.environ["OTEL_TRACES_SAMPLER"] = prev_sampler
    if prev_arg is None:
        os.environ.pop("OTEL_TRACES_SAMPLER_ARG", None)
    else:
        os.environ["OTEL_TRACES_SAMPLER_ARG"] = prev_arg
    return exporter, gateway_instrumentation, worker_instrumentation


def _short_id(job_id: str) -> str:
    return job_id.replace("-", "")[:8]


def _find_span(spans: list, name: str):
    return next(span for span in spans if span.name == name)


def _count_spans(spans: Iterable) -> Counter:
    return Counter(span.name for span in spans)


_HEX_32_RE = re.compile(r"[0-9a-fA-F]{32,}")


def _assert_no_pii(attributes: Mapping[str, object], full_job_id: str) -> None:
    for key, value in attributes.items():
        key_text = str(key).lower()
        assert "tenant" not in key_text
        if isinstance(value, str):
            value_normalized = value.replace("-", "")
            assert full_job_id not in value
            assert "tenant" not in value.lower()
            assert not _HEX_32_RE.search(value_normalized)


def test_trace_context_correlation_and_attributes() -> None:
    exporter, gateway_instr, worker_instr = _install_tracing()
    metrics = get_job_metrics(None)

    job_id = "12345678-aaaa-bbbb-cccc-ffffffffffff"
    queue = "calculator"
    task = "gateway.execute_job"

    with gateway_instr.start_enqueue_span(job_id, queue, task) as enqueue_span:
        headers = gateway_instr.prepare_enqueue_headers(metrics, queue, task)
        assert "traceparent" in headers
        enqueue_context = enqueue_span.get_span_context()

    # Ensure a positive queue wait measurement.
    stamped = int(headers["x-enqueued-at-ms"])
    headers["x-enqueued-at-ms"] = str(stamped - 25)

    with worker_instr.worker_task_span(job_id, queue, task, headers, metrics) as worker_span:
        tracer = trace.get_tracer("worker.jobs")
        for phase in ("deserialize", "compute", "persist", "publish"):
            with tracer.start_as_current_span(f"jobs.{phase}"):
                pass
        worker_span.set_attribute("outcome", "success")

    spans = exporter.get_finished_spans()
    enqueue_span = _find_span(spans, "jobs.enqueue")
    execute_span = _find_span(spans, "jobs.execute")

    assert execute_span.trace_id == enqueue_span.trace_id
    assert execute_span.parent_span_id == enqueue_span.span_id

    extracted_context = extract(headers)
    assert isinstance(extracted_context, SpanContext)
    assert extracted_context.trace_id == execute_span.trace_id

    counts = _count_spans(spans)
    for expected_name in [
        "jobs.enqueue",
        "jobs.execute",
        "jobs.deserialize",
        "jobs.compute",
        "jobs.persist",
        "jobs.publish",
    ]:
        assert counts[expected_name] == 1

    assert execute_span.name == "jobs.execute"
    assert counts["jobs.execute"] == 1
    assert enqueue_span.attributes["job_id_short"] == _short_id(job_id)
    assert execute_span.attributes["job_id_short"] == _short_id(job_id)
    assert len(execute_span.attributes["job_id_short"]) <= 16
    assert execute_span.attributes["job_id_short"] != job_id
    assert execute_span.attributes["queue"] == queue
    assert execute_span.attributes["task"] == task
    assert execute_span.attributes["outcome"] in {"success", "retry", "failed"}
    assert execute_span.attributes["outcome"] == "success"
    assert execute_span.attributes["queue_wait_ms"] > 0
    assert isinstance(execute_span.attributes["queue_wait_ms"], int)
    assert execute_span.attributes["worker_process_ms"] > 0
    assert isinstance(execute_span.attributes["worker_process_ms"], int)

    for phase in ("deserialize", "compute", "persist", "publish"):
        child_span = _find_span(spans, f"jobs.{phase}")
        assert child_span.parent_span_id == execute_span.span_id

    # Guard against PII/high-cardinality leakage.
    _assert_no_pii(enqueue_span.attributes, job_id)
    _assert_no_pii(execute_span.attributes, job_id)


def test_retry_and_failure_emit_events_and_status() -> None:
    exporter, gateway_instr, worker_instr = _install_tracing()
    metrics = get_job_metrics(None)

    job_id = "87654321-bbbb-cccc-dddd-eeeeeeeeeeee"
    queue = "calculator"
    task = "gateway.execute_job"

    with gateway_instr.start_enqueue_span(job_id, queue, task):
        headers = gateway_instr.prepare_enqueue_headers(metrics, queue, task)

    headers["x-enqueued-at-ms"] = str(int(headers["x-enqueued-at-ms"]) - 10)

    with pytest.raises(RuntimeError):
        with worker_instr.worker_task_span(
            job_id,
            queue,
            task,
            headers,
            metrics,
            retry_exception_types=(RuntimeError,),
        ):
            raise RuntimeError("transient issue")

    spans = exporter.get_finished_spans()
    execute_span = _find_span(spans, "jobs.execute")
    counts = _count_spans(spans)
    assert counts["jobs.execute"] == 1
    assert execute_span.attributes["outcome"] == "retry"
    assert execute_span.status.status_code == StatusCode.ERROR
    assert execute_span.attributes["queue_wait_ms"] >= 0
    assert isinstance(execute_span.attributes["queue_wait_ms"], int)
    assert execute_span.attributes["worker_process_ms"] > 0
    assert isinstance(execute_span.attributes["worker_process_ms"], int)
    _assert_no_pii(execute_span.attributes, job_id)
    retry_event = next(event for event in execute_span.events if event.name == "job.retry")
    assert retry_event.attributes["error.type"] == "RuntimeError"
    assert retry_event.attributes["error.message"] == "transient issue"

    exporter.clear()

    with pytest.raises(ValueError):
        with worker_instr.worker_task_span(
            job_id,
            queue,
            task,
            headers,
            metrics,
        ):
            raise ValueError("fatal boom")

    spans = exporter.get_finished_spans()
    execute_span = _find_span(spans, "jobs.execute")
    counts = _count_spans(spans)
    assert counts["jobs.execute"] == 1
    assert execute_span.attributes["outcome"] == "failed"
    assert execute_span.status.status_code == StatusCode.ERROR
    assert execute_span.attributes["queue_wait_ms"] >= 0
    assert isinstance(execute_span.attributes["queue_wait_ms"], int)
    assert execute_span.attributes["worker_process_ms"] > 0
    assert isinstance(execute_span.attributes["worker_process_ms"], int)
    _assert_no_pii(execute_span.attributes, job_id)
    failure_event = next(event for event in execute_span.events if event.name == "job.failed")
    assert failure_event.attributes["error.type"] == "ValueError"
    assert failure_event.attributes["error.message"] == "fatal boom"
    assert any(event.name == "exception" for event in execute_span.events)


def test_worker_span_omits_queue_wait_when_header_missing() -> None:
    exporter, _, worker_instr = _install_tracing()

    job_id = "11223344-aaaa-bbbb-cccc-1234567890ab"
    queue = "calculator"
    task = "gateway.execute_job"

    with worker_instr.worker_task_span(job_id, queue, task, {}, None):
        pass

    spans = exporter.get_finished_spans()
    execute_span = _find_span(spans, "jobs.execute")

    assert execute_span.name == "jobs.execute"
    assert "queue_wait_ms" not in execute_span.attributes
    assert execute_span.attributes["job_id_short"] == _short_id(job_id)
    assert execute_span.attributes["job_id_short"] != job_id
    assert execute_span.attributes["outcome"] == "success"
    assert isinstance(execute_span.attributes["worker_process_ms"], int)
    assert execute_span.attributes["worker_process_ms"] > 0
    _assert_no_pii(execute_span.attributes, job_id)


def test_worker_span_clamps_negative_queue_wait_to_zero() -> None:
    exporter, _, worker_instr = _install_tracing()

    job_id = "11223344-aaaa-bbbb-cccc-1234567890ab"
    queue = "calculator"
    task = "gateway.execute_job"

    headers = {"x-enqueued-at-ms": str(int(time.time() * 1000) + 5000)}

    with worker_instr.worker_task_span(job_id, queue, task, headers, None):
        pass

    spans = exporter.get_finished_spans()
    execute_span = _find_span(spans, "jobs.execute")

    assert execute_span.name == "jobs.execute"
    assert "queue_wait_ms" in execute_span.attributes
    assert isinstance(execute_span.attributes["queue_wait_ms"], int)
    assert execute_span.attributes["queue_wait_ms"] == 0
    assert isinstance(execute_span.attributes["worker_process_ms"], int)
    assert execute_span.attributes["worker_process_ms"] > 0
    _assert_no_pii(execute_span.attributes, job_id)


def test_sampler_env_respected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_TRACES_SAMPLER", "always_off")
    exporter, gateway_instr, worker_instr = _install_tracing()
    metrics = get_job_metrics(None)

    job_id = "facefeed-0000-0000-0000-feedfacefeed"
    queue = "calculator"
    task = "gateway.execute_job"

    with gateway_instr.start_enqueue_span(job_id, queue, task):
        headers = gateway_instr.prepare_enqueue_headers(metrics, queue, task)

    with worker_instr.worker_task_span(job_id, queue, task, headers, metrics):
        pass

    assert exporter.get_finished_spans() == []
