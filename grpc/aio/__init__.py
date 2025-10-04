"""Asyncio-friendly helpers for the lightweight gRPC shim."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Tuple

from .. import (
    AioRpcError,
    ChannelCredentials,
    GenericRpcHandler,
    MetadataItem,
    ServicerContext,
    StatusCode,
    UnaryUnaryRpcMethodHandler,
)


@dataclass
class _PendingResponse:
    data: Any
    trailing_metadata: Sequence[Tuple[str, str]]


class UnaryUnaryMultiCallable:
    def __init__(self, channel: "Channel", method: str) -> None:
        self._channel = channel
        self._method = method

    async def __call__(
        self,
        request: Any,
        timeout: Optional[float] = None,
        metadata: Optional[Sequence[Tuple[str, str]]] = None,
    ) -> Any:
        pending = await self._channel._invoke(self._method, request, timeout, metadata)
        return pending.data


class Channel:
    def __init__(
        self,
        host: str,
        port: int,
        *,
        credentials: ChannelCredentials | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._credentials = credentials

    def unary_unary(self, method: str) -> UnaryUnaryMultiCallable:
        return UnaryUnaryMultiCallable(self, method)

    async def _invoke(
        self,
        method: str,
        request: Any,
        timeout: Optional[float],
        metadata: Optional[Sequence[Tuple[str, str]]],
    ) -> _PendingResponse:
        service, rpc = _split_method(method)
        payload = {
            "service": service,
            "method": rpc,
            "data": request.to_dict(),
            "metadata": [(str(k), str(v)) for k, v in (metadata or ())],
        }
        reader, writer = await asyncio.open_connection(self._host, self._port)
        message = json.dumps(payload).encode("utf-8") + b"\n"
        writer.write(message)
        await writer.drain()
        try:
            if timeout:
                raw = await asyncio.wait_for(reader.readline(), timeout)
            else:
                raw = await reader.readline()
        finally:
            writer.close()
            await writer.wait_closed()
        if not raw:
            raise AioRpcError(StatusCode.UNAVAILABLE, "No response from evaluator")
        response = json.loads(raw.decode("utf-8"))
        trailing_metadata = [(str(k), str(v)) for k, v in response.get("trailing_metadata", [])]
        if "error" in response:
            error = response["error"]
            code_name = error.get("code", "INTERNAL")
            details = error.get("details", "")
            raise AioRpcError(StatusCode[code_name], details, trailing_metadata)
        return _PendingResponse(response.get("data"), trailing_metadata)

    async def close(self) -> None:  # noqa: D401 - compatibility shim
        return None


class Server:
    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, UnaryUnaryRpcMethodHandler]] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._host = "127.0.0.1"
        self._port = 0

    def add_generic_rpc_handlers(self, handlers: list[GenericRpcHandler]) -> None:
        for handler in handlers:
            self._handlers[handler.service_name] = handler.method_handlers

    def add_insecure_port(self, target: str) -> str:
        host, port = target.split(":")
        self._host = host
        self._port = int(port)
        return target

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, self._host, self._port)

    async def wait_for_termination(self) -> None:
        if self._server is None:
            return
        async with self._server:
            await self._server.serve_forever()

    async def stop(self, grace: Optional[float]) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        raw = await reader.readline()
        if not raw:
            writer.close()
            await writer.wait_closed()
            return
        request = json.loads(raw.decode("utf-8"))
        service = request.get("service")
        method = request.get("method")
        data = request.get("data", {})
        metadata_pairs = [(str(k), str(v)) for k, v in request.get("metadata", [])]
        metadata = [MetadataItem(key=k, value=v) for k, v in metadata_pairs]
        peer_info = writer.get_extra_info("peername")
        peer = "" if peer_info is None else f"{peer_info[0]}:{peer_info[1]}"
        context = ServicerContext(metadata=metadata, peer=peer)

        response: dict[str, Any]
        handler = self._handlers.get(service, {}).get(method)
        if handler is None:
            response = {"error": {"code": StatusCode.UNIMPLEMENTED.name, "details": "Unknown RPC"}}
        else:
            try:
                result = await handler(data, context)
            except AioRpcError as exc:  # pragma: no cover - abort path
                response = {
                    "error": {"code": exc.code().name, "details": exc.details()},
                    "trailing_metadata": exc.trailing_metadata(),
                }
            except Exception as exc:  # noqa: BLE001
                response = {
                    "error": {"code": StatusCode.INTERNAL.name, "details": str(exc)},
                    "trailing_metadata": list(context.trailing_metadata()),
                }
            else:
                response = {
                    "data": result,
                    "trailing_metadata": list(context.trailing_metadata()),
                }

        writer.write(json.dumps(response).encode("utf-8") + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()


def insecure_channel(target: str, options: Optional[Iterable[Tuple[str, Any]]] = None) -> Channel:
    host, port = target.split(":")
    return Channel(host, int(port))


def secure_channel(
    target: str,
    credentials: ChannelCredentials,
    options: Optional[Iterable[Tuple[str, Any]]] = None,
) -> Channel:
    host, port = target.split(":")
    return Channel(host, int(port), credentials=credentials)


def server() -> Server:
    return Server()


def _split_method(method: str) -> Tuple[str, str]:
    if not method.startswith("/"):
        raise ValueError("Method must be of the form /package.Service/Method")
    _, service, rpc = method.split("/", 2)
    return service, rpc


__all__ = [
    "Channel",
    "UnaryUnaryMultiCallable",
    "insecure_channel",
    "secure_channel",
    "server",
]
