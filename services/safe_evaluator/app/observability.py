"""Observability helpers for the evaluator service."""

from __future__ import annotations

import contextvars
import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import set_tracer_provider
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from pythonjsonlogger import jsonlogger

from .config import EvaluatorSettings

REQUEST_ID_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "evaluator_request_id", default="-"
)

_DURATION: Histogram | None = None
_INFLIGHT: Gauge | None = None
_SANDBOX_RESTARTS: Counter | None = None
_METRICS_READY = False


class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = REQUEST_ID_CONTEXT.get()
        return True


class _TraceContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        span = trace.get_current_span()
        context = span.get_span_context()
        if context and context.is_valid:
            record.trace_id = format(context.trace_id, "032x")
            record.span_id = format(context.span_id, "016x")
        else:
            record.trace_id = "-"
            record.span_id = "-"
        return True


def configure_logging(settings: EvaluatorSettings) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.addFilter(_TraceContextFilter())
    handler.setFormatter(
        jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(trace_id)s %(span_id)s"
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


def configure_tracing(settings: EvaluatorSettings) -> None:
    resource = Resource.create({"service.name": settings.service_name})
    provider = TracerProvider(resource=resource)
    if settings.otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    set_tracer_provider(provider)
    trace.set_tracer_provider(provider)


def configure_metrics(settings: EvaluatorSettings) -> None:
    global _DURATION, _INFLIGHT, _SANDBOX_RESTARTS, _METRICS_READY
    if _METRICS_READY:
        return

    namespace = settings.metrics_namespace
    _DURATION = Histogram(
        "evaluation_duration_seconds",
        "Distribution of evaluator execution time.",
        namespace=namespace,
        labelnames=("outcome",),
        buckets=(
            0.005,
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
        ),
    )
    _INFLIGHT = Gauge(
        "inflight_requests",
        "Number of evaluation requests currently executing.",
        namespace=namespace,
    )
    _SANDBOX_RESTARTS = Counter(
        "sandbox_restarts_total",
        "Sandbox processes restarted after failures.",
        namespace=namespace,
        labelnames=("reason",),
    )
    start_http_server(settings.metrics_port)
    _METRICS_READY = True


def record_evaluation(duration_seconds: float, outcome: str) -> None:
    if _DURATION is None:
        return
    _DURATION.labels(outcome=outcome).observe(duration_seconds)


def increment_inflight() -> None:
    if _INFLIGHT is None:
        return
    _INFLIGHT.inc()


def decrement_inflight() -> None:
    if _INFLIGHT is None:
        return
    _INFLIGHT.dec()


def record_sandbox_restart(reason: str) -> None:
    if _SANDBOX_RESTARTS is None:
        return
    _SANDBOX_RESTARTS.labels(reason=reason).inc()


def set_request_id(request_id: str) -> contextvars.Token[str]:
    return REQUEST_ID_CONTEXT.set(request_id)


def reset_request_id(token: contextvars.Token[str]) -> None:
    REQUEST_ID_CONTEXT.reset(token)
*** End of File ***
