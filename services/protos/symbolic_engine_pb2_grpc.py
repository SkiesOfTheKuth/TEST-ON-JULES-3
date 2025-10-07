"""gRPC stubs for the symbolic engine service."""
from __future__ import annotations

from typing import Sequence

from services.common.grpc import grpc

from . import symbolic_engine_pb2 as symbolic__pb2


class SymbolicEngineStub:
    """Async client stub for the symbolic engine service."""

    def __init__(self, channel: grpc.aio.Channel) -> None:
        self._channel = channel

    async def Simplify(
        self,
        request: symbolic__pb2.SimplifyRequest,
        timeout: float | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
    ) -> symbolic__pb2.SymbolicResponse:
        callable_ = self._channel.unary_unary("/symbolic.SymbolicEngine/Simplify")
        response_payload = await callable_(request, timeout=timeout, metadata=metadata)
        return symbolic__pb2.SymbolicResponse.from_dict(response_payload)

    async def Derivative(
        self,
        request: symbolic__pb2.DerivativeRequest,
        timeout: float | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
    ) -> symbolic__pb2.SymbolicResponse:
        callable_ = self._channel.unary_unary("/symbolic.SymbolicEngine/Derivative")
        response_payload = await callable_(request, timeout=timeout, metadata=metadata)
        return symbolic__pb2.SymbolicResponse.from_dict(response_payload)

    async def Integral(
        self,
        request: symbolic__pb2.IntegralRequest,
        timeout: float | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
    ) -> symbolic__pb2.SymbolicResponse:
        callable_ = self._channel.unary_unary("/symbolic.SymbolicEngine/Integral")
        response_payload = await callable_(request, timeout=timeout, metadata=metadata)
        return symbolic__pb2.SymbolicResponse.from_dict(response_payload)

    async def Solve(
        self,
        request: symbolic__pb2.SolveRequest,
        timeout: float | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
    ) -> symbolic__pb2.SymbolicResponse:
        callable_ = self._channel.unary_unary("/symbolic.SymbolicEngine/Solve")
        response_payload = await callable_(request, timeout=timeout, metadata=metadata)
        return symbolic__pb2.SymbolicResponse.from_dict(response_payload)

    async def Series(
        self,
        request: symbolic__pb2.SeriesRequest,
        timeout: float | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
    ) -> symbolic__pb2.SymbolicResponse:
        callable_ = self._channel.unary_unary("/symbolic.SymbolicEngine/Series")
        response_payload = await callable_(request, timeout=timeout, metadata=metadata)
        return symbolic__pb2.SymbolicResponse.from_dict(response_payload)

    async def Codegen(
        self,
        request: symbolic__pb2.CodegenRequest,
        timeout: float | None = None,
        metadata: Sequence[tuple[str, str]] | None = None,
    ) -> symbolic__pb2.SymbolicResponse:
        callable_ = self._channel.unary_unary("/symbolic.SymbolicEngine/Codegen")
        response_payload = await callable_(request, timeout=timeout, metadata=metadata)
        return symbolic__pb2.SymbolicResponse.from_dict(response_payload)


class SymbolicEngineServicer:
    """Base servicer implementation expected by the gateway."""

    async def Simplify(self, request: symbolic__pb2.SimplifyRequest, context: grpc.ServicerContext) -> symbolic__pb2.SymbolicResponse:  # noqa: D401,E501
        raise NotImplementedError

    async def Derivative(self, request: symbolic__pb2.DerivativeRequest, context: grpc.ServicerContext) -> symbolic__pb2.SymbolicResponse:
        raise NotImplementedError

    async def Integral(self, request: symbolic__pb2.IntegralRequest, context: grpc.ServicerContext) -> symbolic__pb2.SymbolicResponse:
        raise NotImplementedError

    async def Solve(self, request: symbolic__pb2.SolveRequest, context: grpc.ServicerContext) -> symbolic__pb2.SymbolicResponse:
        raise NotImplementedError

    async def Series(self, request: symbolic__pb2.SeriesRequest, context: grpc.ServicerContext) -> symbolic__pb2.SymbolicResponse:
        raise NotImplementedError

    async def Codegen(self, request: symbolic__pb2.CodegenRequest, context: grpc.ServicerContext) -> symbolic__pb2.SymbolicResponse:
        raise NotImplementedError


def add_SymbolicEngineServicer_to_server(servicer: SymbolicEngineServicer, server: grpc.aio.Server) -> None:
    async def _handle(method_name: str, payload: dict, context: grpc.ServicerContext) -> dict:
        request_cls = {
            "Simplify": symbolic__pb2.SimplifyRequest,
            "Derivative": symbolic__pb2.DerivativeRequest,
            "Integral": symbolic__pb2.IntegralRequest,
            "Solve": symbolic__pb2.SolveRequest,
            "Series": symbolic__pb2.SeriesRequest,
            "Codegen": symbolic__pb2.CodegenRequest,
        }[method_name]
        request = request_cls.from_dict(payload)
        handler = getattr(servicer, method_name)
        response = await handler(request, context)
        return response.to_dict()

    handlers = {}
    for method_name in ("Simplify", "Derivative", "Integral", "Solve", "Series", "Codegen"):
        async def _invoker(payload: dict, context: grpc.ServicerContext, *, _method=method_name):
            return await _handle(_method, payload, context)

        handlers[method_name] = grpc.UnaryUnaryRpcMethodHandler(_invoker)

    generic_handler = grpc.method_handlers_generic_handler("symbolic.SymbolicEngine", handlers)
    server.add_generic_rpc_handlers([generic_handler])


__all__ = [
    "SymbolicEngineStub",
    "SymbolicEngineServicer",
    "add_SymbolicEngineServicer_to_server",
]
