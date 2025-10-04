"""Entrypoint for the safe evaluator microservice."""

from __future__ import annotations

import asyncio
import logging

import grpc

from .config import get_settings
from .observability import configure_logging, configure_metrics, configure_tracing
from .service import EvaluatorService
from services.protos import evaluator_pb2_grpc

logger = logging.getLogger(__name__)


async def serve() -> None:
    settings = get_settings()
    configure_logging(settings)
    configure_tracing(settings)
    configure_metrics(settings)

    server = grpc.aio.server()
    evaluator = EvaluatorService(settings)
    evaluator_pb2_grpc.add_EvaluatorServicer_to_server(evaluator, server)
    server.add_insecure_port(f"{settings.host}:{settings.port}")
    logger.info("Starting evaluator", extra={"host": settings.host, "port": settings.port})
    await server.start()
    await server.wait_for_termination()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()
