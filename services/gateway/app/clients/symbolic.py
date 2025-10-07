"""Gateway client for the Symbolic Engine gRPC service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from services.common.grpc import aio
from services.protos import symbolic_engine_pb2 as symbolic_pb2
from services.protos import symbolic_engine_pb2_grpc as symbolic_grpc


@dataclass
class SymbolicEngineConfig:
    host: str
    port: int
    secure: bool = False


class SymbolicEngineClient:
    """Async client wrapper around the generated SymbolicEngine stub."""

    def __init__(self, config: SymbolicEngineConfig, *, channel: aio.Channel | None = None) -> None:
        self._config = config
        credentials = aio.ChannelCredentials() if config.secure else None
        self._channel = channel or aio.Channel(config.host, config.port, credentials=credentials)
        self._stub = symbolic_grpc.SymbolicEngineStub(self._channel)

    async def simplify(
        self,
        expression: str,
        *,
        variables: Sequence[str] | None = None,
        method: str | None = None,
        canonicalize: bool = True,
        timeout: float | None = None,
    ) -> symbolic_pb2.SymbolicResponse:
        request = symbolic_pb2.SimplifyRequest(
            expression=expression,
            variables=list(variables or []),
            canonicalize=canonicalize,
            method=method or "",
        )
        return await self._stub.Simplify(request, timeout=timeout)

    async def derivative(
        self,
        expression: str,
        *,
        variable: str,
        order: int = 1,
        variables: Sequence[str] | None = None,
        canonicalize: bool = True,
        timeout: float | None = None,
    ) -> symbolic_pb2.SymbolicResponse:
        request = symbolic_pb2.DerivativeRequest(
            expression=expression,
            variables=list(variables or []),
            variable=variable,
            order=order,
            canonicalize=canonicalize,
        )
        return await self._stub.Derivative(request, timeout=timeout)

    async def integral(
        self,
        expression: str,
        *,
        variable: str,
        lower_limit: Optional[str] = None,
        upper_limit: Optional[str] = None,
        variables: Sequence[str] | None = None,
        canonicalize: bool = True,
        timeout: float | None = None,
    ) -> symbolic_pb2.SymbolicResponse:
        request = symbolic_pb2.IntegralRequest(
            expression=expression,
            variables=list(variables or []),
            variable=variable,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
            canonicalize=canonicalize,
        )
        return await self._stub.Integral(request, timeout=timeout)

    async def solve(
        self,
        equation: str,
        *,
        variable: str,
        parameters: Iterable[str] | None = None,
        canonicalize: bool = True,
        timeout: float | None = None,
    ) -> symbolic_pb2.SymbolicResponse:
        request = symbolic_pb2.SolveRequest(
            equation=equation,
            variable=variable,
            parameters=list(parameters or []),
            canonicalize=canonicalize,
        )
        return await self._stub.Solve(request, timeout=timeout)

    async def series(
        self,
        expression: str,
        *,
        variable: str,
        point: str = "0",
        order: int = 6,
        variables: Sequence[str] | None = None,
        canonicalize: bool = True,
        timeout: float | None = None,
    ) -> symbolic_pb2.SymbolicResponse:
        request = symbolic_pb2.SeriesRequest(
            expression=expression,
            variables=list(variables or []),
            variable=variable,
            point=point,
            order=order,
            canonicalize=canonicalize,
        )
        return await self._stub.Series(request, timeout=timeout)

    async def codegen(
        self,
        expression: str,
        *,
        variables: Sequence[str] | None = None,
        target: str = "c",
        function_name: str = "symbolic_kernel",
        emit_header: bool = False,
        canonicalize: bool = True,
        timeout: float | None = None,
    ) -> symbolic_pb2.SymbolicResponse:
        request = symbolic_pb2.CodegenRequest(
            expression=expression,
            variables=list(variables or []),
            target=target,
            function_name=function_name,
            emit_header=emit_header,
            canonicalize=canonicalize,
        )
        return await self._stub.Codegen(request, timeout=timeout)

    async def close(self) -> None:
        await self._channel.close()
