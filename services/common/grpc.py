"""Compatibility layer for gRPC imports.

The production code depends on ``grpcio``.  When the compiled package is not
available (for example in offline kata environments), we fall back to the
lightweight shim that lives in :mod:`calculator_grpc` so the rest of the
application continues to run.  The shim implements the tiny subset of the
``grpc`` API that our services rely on, including asyncio support and TLS
handling.
"""

from __future__ import annotations

try:  # pragma: no cover - exercised when grpcio is installed
    import grpc as _grpc  # type: ignore
    from grpc import aio as _grpc_aio  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised in kata runtime
    from calculator_grpc import aio as _grpc_aio  # type: ignore
    import calculator_grpc as _grpc  # type: ignore

grpc = _grpc
aio = _grpc_aio

__all__ = ["grpc", "aio"]
