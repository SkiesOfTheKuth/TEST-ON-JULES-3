"""Lightweight asyncio-compatible gRPC shims for the kata environment."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple


class StatusCode(Enum):
    OK = 0
    CANCELLED = 1
    UNKNOWN = 2
    INVALID_ARGUMENT = 3
    DEADLINE_EXCEEDED = 4
    NOT_FOUND = 5
    ALREADY_EXISTS = 6
    PERMISSION_DENIED = 7
    RESOURCE_EXHAUSTED = 8
    FAILED_PRECONDITION = 9
    ABORTED = 10
    OUT_OF_RANGE = 11
    UNIMPLEMENTED = 12
    INTERNAL = 13
    UNAVAILABLE = 14
    DATA_LOSS = 15
    UNAUTHENTICATED = 16


class RpcError(Exception):
    def __init__(
        self,
        code: StatusCode,
        details: str = "",
        trailing_metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> None:
        super().__init__(details)
        self._code = code
        self._details = details
        self._trailing_metadata = list(trailing_metadata or [])

    def code(self) -> StatusCode:
        return self._code

    def details(self) -> str:
        return self._details

    def trailing_metadata(self) -> List[Tuple[str, str]]:
        return list(self._trailing_metadata)


class AioRpcError(RpcError):
    """Exception raised when an asyncio RPC fails."""


@dataclass(slots=True)
class MetadataItem:
    key: str
    value: str


@dataclass(slots=True)
class ChannelCredentials:
    root_certificates: Optional[bytes] = None
    private_key: Optional[bytes] = None
    certificate_chain: Optional[bytes] = None


def ssl_channel_credentials(
    root_certificates: Optional[bytes] = None,
    private_key: Optional[bytes] = None,
    certificate_chain: Optional[bytes] = None,
) -> ChannelCredentials:
    return ChannelCredentials(root_certificates, private_key, certificate_chain)


class UnaryUnaryRpcMethodHandler:
    def __init__(self, coroutine: Callable[[Any, "ServicerContext"], Awaitable[Any]]) -> None:
        self._coroutine = coroutine

    async def __call__(self, request: Any, context: "ServicerContext") -> Any:
        return await self._coroutine(request, context)


@dataclass(slots=True)
class GenericRpcHandler:
    service_name: str
    method_handlers: Dict[str, UnaryUnaryRpcMethodHandler]


class ServicerContext:
    def __init__(
        self,
        metadata: Sequence[MetadataItem] | None = None,
        peer: str = "",
    ) -> None:
        self._metadata = tuple(metadata or ())
        self._peer = peer
        self._trailing_metadata: List[Tuple[str, str]] = []

    def invocation_metadata(self) -> Tuple[MetadataItem, ...]:
        return self._metadata

    def set_trailing_metadata(self, metadata: Sequence[Tuple[str, str]]) -> None:
        self._trailing_metadata = [(str(key), str(value)) for key, value in metadata]

    def trailing_metadata(self) -> Tuple[Tuple[str, str], ...]:
        return tuple(self._trailing_metadata)

    def peer(self) -> str:
        return self._peer

    async def abort(self, code: StatusCode, details: str) -> None:
        raise AioRpcError(code, details, self._trailing_metadata)


def method_handlers_generic_handler(
    service_name: str,
    handlers: Dict[str, UnaryUnaryRpcMethodHandler],
) -> GenericRpcHandler:
    return GenericRpcHandler(service_name, handlers)


from . import aio  # noqa: E402

__all__ = [
    "AioRpcError",
    "ChannelCredentials",
    "GenericRpcHandler",
    "MetadataItem",
    "RpcError",
    "ServicerContext",
    "StatusCode",
    "UnaryUnaryRpcMethodHandler",
    "aio",
    "method_handlers_generic_handler",
    "ssl_channel_credentials",
]
