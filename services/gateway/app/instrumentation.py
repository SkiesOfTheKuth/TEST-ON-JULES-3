"""Observability helpers for the gateway service."""

from __future__ import annotations

import contextvars
from collections import deque
import logging
import time
import uuid
from typing import Awaitable, Callable

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)
from opentelemetry.trace import set_tracer_provider
from prometheus_client import Counter, Gauge, Histogram, REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator
from pythonjsonlogger import jsonlogger
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from .config import GatewaySettings, get_settings

logger = logging.getLogger(__name__)

REQUEST_ID_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "gateway_request_id", default="-"
)

TENANT_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "gateway_tenant", default="-"
)
QUEUE_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "gateway_queue", default="-"
)
POLICY_CONTEXT: contextvars.ContextVar[str] = contextvars.ContextVar(
    "gateway_policy_outcome", default="unknown"
)

_REQUEST_COUNTER: Counter | None = None
_REQUEST_LATENCY: Histogram | None = None
_RATE_LIMIT_REJECTIONS: Gauge | None = None
_RATE_LIMIT_HISTORY: dict[str, deque[float]] = {}
_METRICS_INITIALIZED = False
_FASTAPI_INSTRUMENTED = False

settings = get_settings()
_METRIC_NAMESPACE = settings.observability.metrics_namespace


def _register_metric(name: str, factory):
    full_name = f"{_METRIC_NAMESPACE}_{name}" if _METRIC_NAMESPACE else name
    try:
        return factory()
    except ValueError:
        existing = getattr(REGISTRY, '_names_to_collectors', {}).get(full_name)
        if existing is None:
            raise
        return existing


_POLICY_DECISIONS = _register_metric(
    'policy_decisions_total',
    lambda: Counter(
        'policy_decisions_total',
        'Count of policy engine evaluation outcomes.',
        labelnames=('tenant', 'rule', 'decision'),
        namespace=_METRIC_NAMESPACE,
    ),
)
_POLICY_VIOLATIONS = _register_metric(
    'policy_violations_total',
    lambda: Counter(
        'policy_violations_total',
        'Count of policy evaluations resulting in enforcement.',
        labelnames=('tenant', 'rule'),
        namespace=_METRIC_NAMESPACE,
    ),
)


class _RequestIdFilter(logging.Filter):
    """Inject the active request identifier into log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.request_id = REQUEST_ID_CONTEXT.get()
        return True


class _TraceContextFilter(logging.Filter):
    """Attach trace identifiers from the current span to log records."""

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

class _JobMetadataFilter(logging.Filter):
    """Attach queue/policy/tenant metadata to log records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        record.tenant = TENANT_CONTEXT.get()
        record.queue = QUEUE_CONTEXT.get()
        record.policy_outcome = POLICY_CONTEXT.get()
        return True



class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Capture request level metrics and manage request context."""

    def __init__(self, app: FastAPI, settings: GatewaySettings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = REQUEST_ID_CONTEXT.set(request_id)
        tenant_token = TENANT_CONTEXT.set("-")
        queue_token = QUEUE_CONTEXT.set("-")
        policy_token = POLICY_CONTEXT.set("unknown")
        request.state.request_id = request_id

        start_time = time.perf_counter()
        status_code = 500
        endpoint = request.url.path
        try:
            response = await call_next(request)
            status_code = response.status_code
            route = request.scope.get("route")
            if route and getattr(route, "path", None):
                endpoint = route.path  # type: ignore[assignment]
        except Exception as exc:  # noqa: BLE001
            duration = time.perf_counter() - start_time
            logger.exception("Request failed", exc_info=exc)
            _observe_request(request, endpoint, status_code, duration)
            raise
        else:
            duration = time.perf_counter() - start_time
            _observe_request(request, endpoint, status_code, duration)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            REQUEST_ID_CONTEXT.reset(token)
            TENANT_CONTEXT.reset(tenant_token)
            QUEUE_CONTEXT.reset(queue_token)
            POLICY_CONTEXT.reset(policy_token)


def _observe_request(request: Request, endpoint: str, status_code: int, duration: float) -> None:
    if not _REQUEST_COUNTER or not _REQUEST_LATENCY:
        return
    labels = {
        "endpoint": endpoint,
        "method": request.method,
        "status": str(status_code),
    }
    _REQUEST_COUNTER.labels(**labels).inc()
    _REQUEST_LATENCY.labels(**labels).observe(duration)
    _cleanup_rate_limit_history()


def configure_logging(settings: GatewaySettings) -> None:
    handler = logging.StreamHandler()
    handler.addFilter(_RequestIdFilter())
    handler.addFilter(_TraceContextFilter())
    handler.addFilter(_JobMetadataFilter())
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s %(tenant)s %(queue)s %(policy_outcome)s %(trace_id)s %(span_id)s")
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))


def configure_tracing(settings: GatewaySettings) -> None:
    resource = Resource.create({"service.name": settings.observability.service_name})
    provider = TracerProvider(resource=resource)
    if settings.observability.otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.observability.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    set_tracer_provider(provider)
    trace.set_tracer_provider(provider)


def _configure_metrics(settings: GatewaySettings) -> None:
    global _REQUEST_COUNTER, _REQUEST_LATENCY, _RATE_LIMIT_REJECTIONS, _METRICS_INITIALIZED
    if _METRICS_INITIALIZED:
        return

    namespace = settings.observability.metrics_namespace
    _REQUEST_COUNTER = Counter(
        "requests_total",
        "Gateway requests by endpoint, method and status.",
        labelnames=("endpoint", "method", "status"),
        namespace=namespace,
    )
    _REQUEST_LATENCY = Histogram(
        "request_latency_seconds",
        "Latency histogram for gateway requests.",
        labelnames=("endpoint", "method", "status"),
        namespace=namespace,
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
    _RATE_LIMIT_REJECTIONS = Gauge(
        "rate_limit_rejections",
        "Count of requests rejected by gateway rate limiting.",
        labelnames=("reason",),
        namespace=namespace,
    )
    _METRICS_INITIALIZED = True


def instrument_app(app: FastAPI, settings: GatewaySettings) -> None:
    global _FASTAPI_INSTRUMENTED
    _configure_metrics(settings)

    if not _FASTAPI_INSTRUMENTED:
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=trace.get_tracer_provider(),
            excluded_urls="/metrics",
        )
        _FASTAPI_INSTRUMENTED = True

    app.add_middleware(ObservabilityMiddleware, settings=settings)
    Instrumentator().instrument(app).expose(app)


def record_rate_limit_rejection(reason: str) -> None:
    if not _RATE_LIMIT_REJECTIONS:
        return
    now = time.time()
    history = _RATE_LIMIT_HISTORY.setdefault(reason, deque())
    history.append(now)
    cutoff = now - 60
    while history and history[0] < cutoff:
        history.popleft()
    _RATE_LIMIT_REJECTIONS.labels(reason=reason).set(len(history))


def _cleanup_rate_limit_history() -> None:
    if not _RATE_LIMIT_REJECTIONS:
        return
    cutoff = time.time() - 60
    for reason, history in _RATE_LIMIT_HISTORY.items():
        while history and history[0] < cutoff:
            history.popleft()
        _RATE_LIMIT_REJECTIONS.labels(reason=reason).set(len(history))


def get_request_id() -> str:
    return REQUEST_ID_CONTEXT.get()



def set_tenant_context(tenant: str) -> None:
    TENANT_CONTEXT.set((tenant or '-').strip() or '-')


def set_queue_context(queue: str) -> None:
    QUEUE_CONTEXT.set((queue or '-').strip() or '-')


def set_policy_context(decision: str) -> None:
    POLICY_CONTEXT.set((decision or 'unknown').strip() or 'unknown')


def get_tenant_context() -> str:
    return TENANT_CONTEXT.get()


def get_queue_context() -> str:
    return QUEUE_CONTEXT.get()


def get_policy_context() -> str:
    return POLICY_CONTEXT.get()


def record_policy_decision(*, tenant: str, rule: str, decision: str) -> None:
    normalized_tenant = (tenant or '-').strip() or '-'
    normalized_rule = (rule or 'unspecified').strip() or 'unspecified'
    normalized_decision = (decision or 'unknown').strip() or 'unknown'
    set_tenant_context(normalized_tenant)
    set_policy_context(normalized_decision)
    _POLICY_DECISIONS.labels(tenant=normalized_tenant, rule=normalized_rule, decision=normalized_decision).inc()
    if normalized_decision.lower() not in {'allow', 'pass'}:
        _POLICY_VIOLATIONS.labels(tenant=normalized_tenant, rule=normalized_rule).inc()
