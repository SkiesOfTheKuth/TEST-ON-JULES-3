"""Very small asyncio RPC transport used as a stand-in for grpc.aio."""

from __future__ import annotations

import asyncio
import json

from typing import Any, Awaitable, Callable, Dict, Optional

from .. import AioRpcError, GenericRpcHandler, ServicerContext, StatusCode


class UnaryUnaryMultiCallable:
    def __init__(self, channel: "Channel", method: str) -> None:
        self._channel = channel
        self._method = method

    async def __call__(self, request: Any, timeout: Optional[float] = None, metadata: Any = None) -> Any:
        return await self._channel._invoke(self._method, request, timeout)


class Channel:
    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    def unary_unary(self, method: str) -> UnaryUnaryMultiCallable:
        return UnaryUnaryMultiCallable(self, method)

    async def _invoke(self, method: str, request: Any, timeout: Optional[float]) -> Any:
        service, rpc = _split_method(method)
        payload = {"service": service, "method": rpc, "data": request.to_dict()}
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
        if "error" in response:
            error = response["error"]
            raise AioRpcError(StatusCode[error.get("code", "INTERNAL")], error.get("details", ""))
        return response["data"]

    async def close(self) -> None:
        return None


class Server:
    def __init__(self) -> None:
        self._handlers: Dict[str, Dict[str, Callable[[Any, ServicerContext], Awaitable[Any]]]] = {}
        self._server: Optional[asyncio.base_events.Server] = None
        self._host = "127.0.0.1"
        self._port = 0

    def add_generic_rpc_handlers(self, handlers: list[GenericRpcHandler]) -> None:
        for handler in handlers:
            self._handlers[handler.service_name] = {
                name: method.__call__ for name, method in handler.method_handlers.items()
            }

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
        response: Dict[str, Any]
        try:
            handler = self._handlers[service][method]
            context = ServicerContext()
            result = await handler(data, context)
        except AioRpcError as exc:
            response = {"error": {"code": exc.code().name, "details": exc.details()}}
        except Exception as exc:  # noqa: BLE001
            response = {"error": {"code": StatusCode.INTERNAL.name, "details": str(exc)}}
        else:
            response = {"data": result}
        writer.write(json.dumps(response).encode("utf-8") + b"\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()


def insecure_channel(target: str) -> Channel:
    host, port = target.split(":")
    return Channel(host, int(port))


def server() -> Server:
    return Server()


def _split_method(method: str) -> tuple[str, str]:
    if not method.startswith("/"):
        raise ValueError("Method must be of the form /package.Service/Method")
    _, service, rpc = method.split("/", 2)
    return service, rpc


__all__ = [
    "Channel",
    "Server",
    "UnaryUnaryMultiCallable",
    "insecure_channel",
    "server",
]
