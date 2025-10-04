"""Observability helpers."""

from __future__ import annotations

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import set_tracer_provider
from prometheus_fastapi_instrumentator import Instrumentator

from .config import GatewaySettings

logger = logging.getLogger(__name__)


def configure_tracing(settings: GatewaySettings) -> None:
    resource = Resource.create({"service.name": settings.observability.service_name})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=settings.observability.otlp_endpoint) if settings.observability.otlp_endpoint else None
    if exporter:
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    set_tracer_provider(provider)
    trace.set_tracer_provider(provider)


def instrument_app(app, settings: GatewaySettings) -> None:
    Instrumentator(namespace=settings.observability.metrics_namespace).instrument(app).expose(app)
