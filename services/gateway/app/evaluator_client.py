"""Helpers for interacting with the evaluator gRPC service."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from opentelemetry.propagate import inject

from services.common.grpc import aio as grpc_aio
from services.common.grpc import grpc

from .config import EvaluatorSettings


def create_async_channel(settings: EvaluatorSettings) -> grpc_aio.Channel:
    """Return an asynchronous gRPC channel for the evaluator."""

    return _create_channel(settings, asynchronous=True)


def create_sync_channel(settings: EvaluatorSettings) -> grpc.Channel:
    """Return a synchronous gRPC channel for the evaluator."""

    return _create_channel(settings, asynchronous=False)


def build_grpc_metadata(*, request_id: Optional[str] = None, extra: Optional[Dict[str, str]] = None) -> list[tuple[str, str]]:
    """Construct gRPC metadata including the current OpenTelemetry context."""

    carrier: Dict[str, str] = {}
    inject(carrier)
    metadata = list(carrier.items())
    if request_id:
        metadata.append(("x-request-id", request_id))
    if extra:
        metadata.extend(extra.items())
    return metadata


def _create_channel(settings: EvaluatorSettings, *, asynchronous: bool):
    target = f"{settings.host}:{settings.port}"
    if settings.use_tls:
        credentials = grpc.ssl_channel_credentials(
            root_certificates=_read_optional_bytes(settings.root_cert_path),
            private_key=_read_optional_bytes(settings.client_key_path),
            certificate_chain=_read_optional_bytes(settings.client_cert_path),
        )
        if asynchronous:
            return grpc_aio.secure_channel(target, credentials)
        return grpc.secure_channel(target, credentials)
    if asynchronous:
        return grpc_aio.insecure_channel(target)
    return grpc.insecure_channel(target)


def _read_optional_bytes(path: Optional[Path]) -> Optional[bytes]:
    if path is None:
        return None
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise RuntimeError(f"gRPC credential file not found: {resolved}")
    return resolved.read_bytes()

