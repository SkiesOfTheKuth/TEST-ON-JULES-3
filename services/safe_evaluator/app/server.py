"""Entrypoint for the safe evaluator microservice."""

from __future__ import annotations

import asyncio
import logging

import grpc
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor

from .config import EvaluatorSettings, get_settings
from .service import EvaluatorService
from services.protos import evaluator_pb2_grpc

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO))


def configure_tracing(settings: EvaluatorSettings) -> None:
    resource = Resource.create({"service.name": "calculator-safe-evaluator"})
    provider = TracerProvider(resource=resource)
    if settings.otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


async def serve() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings)

    server = grpc.aio.server()
    evaluator = EvaluatorService(settings)
    evaluator_pb2_grpc.add_EvaluatorServicer_to_server(evaluator, server)
    server.add_insecure_port(f"{settings.host}:{settings.port}")
    logger.info("Starting evaluator on %s:%s", settings.host, settings.port)
    await server.start()
    await server.wait_for_termination()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
