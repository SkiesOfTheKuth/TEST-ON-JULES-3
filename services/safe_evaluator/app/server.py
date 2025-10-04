"""Entrypoint for the safe evaluator microservice."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from services.common.grpc import grpc

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
    endpoint = f"{settings.host}:{settings.port}"
    if settings.use_tls:
        credentials = _build_server_credentials(
            settings.server_key_path,
            settings.server_cert_path,
            settings.client_ca_path,
        )
        server.add_secure_port(endpoint, credentials)
        logger.info(
            "Starting evaluator with TLS",
            extra={"host": settings.host, "port": settings.port, "require_client_auth": settings.client_ca_path is not None},
        )
    else:
        server.add_insecure_port(endpoint)
        logger.info("Starting evaluator", extra={"host": settings.host, "port": settings.port})
    await server.start()
    await server.wait_for_termination()


def main() -> None:
    asyncio.run(serve())


if __name__ == "__main__":
    main()


def _build_server_credentials(
    key_path: Optional[Path],
    cert_path: Optional[Path],
    client_ca_path: Optional[Path],
) -> grpc.ServerCredentials:
    private_key = _read_required_bytes(key_path, "server private key")
    certificate_chain = _read_required_bytes(cert_path, "server certificate")
    root_certificates = _read_optional_bytes(client_ca_path)
    require_client_auth = root_certificates is not None
    return grpc.ssl_server_credentials(
        [(private_key, certificate_chain)],
        root_certificates=root_certificates,
        require_client_auth=require_client_auth,
    )


def _read_required_bytes(path: Optional[Path], description: str) -> bytes:
    if path is None:
        raise RuntimeError(f"TLS configuration missing {description}")
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise RuntimeError(f"TLS file not found: {resolved}")
    return resolved.read_bytes()


def _read_optional_bytes(path: Optional[Path]) -> Optional[bytes]:
    if path is None:
        return None
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise RuntimeError(f"TLS file not found: {resolved}")
    return resolved.read_bytes()
