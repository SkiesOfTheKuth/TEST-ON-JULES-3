"""Compatibility layer for gRPC imports.

The production code depends on ``grpcio``.  When the compiled package is not
available (for example in offline kata environments), we fall back to the
lightweight shim that lives in :mod:`calculator_grpc` so the rest of the
application continues to run.  The shim implements the tiny subset of the
``grpc`` API that our services rely on, including asyncio support and TLS
handling.
"""

from __future__ import annotations

import os

_USE_NATIVE_GRPC = os.getenv("CALCULATOR_USE_NATIVE_GRPC", "").lower() in {"1", "true", "yes"}

if _USE_NATIVE_GRPC:
    try:  # pragma: no cover - exercised when grpcio is installed
        import grpc as _grpc  # type: ignore
        from grpc import aio as _grpc_aio  # type: ignore
    except ModuleNotFoundError:  # pragma: no cover - fallback when native build missing
        _USE_NATIVE_GRPC = False

if not _USE_NATIVE_GRPC:
    from calculator_grpc import aio as _grpc_aio  # type: ignore
    import calculator_grpc as _grpc  # type: ignore
else:  # pragma: no cover - executed when native grpcio is available
    if not hasattr(_grpc, 'UnaryUnaryRpcMethodHandler'):
        _grpc.UnaryUnaryRpcMethodHandler = _grpc.unary_unary_rpc_method_handler  # type: ignore[attr-defined]

    if hasattr(_grpc_aio, 'server'):
        _native_server = _grpc_aio.server

        class _ServerProxy:
            __slots__ = ('_server', 'bound_port')

            def __init__(self, server):
                self._server = server
                self.bound_port = None

            def add_insecure_port(self, target, *args, **kwargs):
                port = self._server.add_insecure_port(target, *args, **kwargs)
                self.bound_port = port
                return port

            def add_secure_port(self, target, credentials, *args, **kwargs):
                port = self._server.add_secure_port(target, credentials, *args, **kwargs)
                self.bound_port = port
                return port

            def __getattr__(self, item):
                return getattr(self._server, item)

        def _server_factory(*args, **kwargs):
            return _ServerProxy(_native_server(*args, **kwargs))

        _grpc_aio.server = _server_factory  # type: ignore[assignment]


grpc = _grpc
aio = _grpc_aio

__all__ = ["grpc", "aio"]
