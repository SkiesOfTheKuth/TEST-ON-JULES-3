"""Minimal asynchronous RPC layer used for offline gRPC development."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict


class StatusCode(Enum):
    OK = 0
    INVALID_ARGUMENT = 3
    DEADLINE_EXCEEDED = 4
    NOT_FOUND = 5
    PERMISSION_DENIED = 7
    RESOURCE_EXHAUSTED = 8
    INTERNAL = 13
    UNAVAILABLE = 14


class RpcError(Exception):
    def __init__(self, code: StatusCode, details: str = "") -> None:
        self._code = code
        self._details = details
        super().__init__(details)

    def code(self) -> StatusCode:
        return self._code

    def details(self) -> str:
        return self._details


class AioRpcError(RpcError):
    pass


@dataclass
class GenericRpcHandler:
    service_name: str
    method_handlers: Dict[str, "UnaryUnaryRpcMethodHandler"]


class UnaryUnaryRpcMethodHandler:
    def __init__(self, coroutine: Callable[[Any, "ServicerContext"], Awaitable[Any]]) -> None:
        self._coroutine = coroutine

    async def __call__(self, request: Any, context: "ServicerContext") -> Any:
        return await self._coroutine(request, context)


class ServicerContext:
    async def abort(self, code: StatusCode, details: str) -> None:
        raise AioRpcError(code, details)


def method_handlers_generic_handler(service_name: str, handlers: Dict[str, UnaryUnaryRpcMethodHandler]) -> GenericRpcHandler:
    return GenericRpcHandler(service_name, handlers)


from . import aio  # noqa: E402  (import at end to avoid circular import)

__all__ = [
    "StatusCode",
    "RpcError",
    "AioRpcError",
    "ServicerContext",
    "UnaryUnaryRpcMethodHandler",
    "GenericRpcHandler",
    "method_handlers_generic_handler",
    "aio",
]
