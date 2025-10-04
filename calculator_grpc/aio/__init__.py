"""Asyncio-friendly helpers for the lightweight gRPC shim."""

from __future__ import annotations

import asyncio
import json
import os
import ssl
import tempfile
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence, Tuple

from .. import (
    AioRpcError,
    ChannelCredentials,
    GenericRpcHandler,
    MetadataItem,
    ServerCredentials,
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
        ssl_context_cm = (
            _client_ssl_context(self._credentials)
            if self._credentials
            else nullcontext(None)
        )
        with ssl_context_cm as ssl_context:
            connect_kwargs = {}
            if ssl_context is not None:
                connect_kwargs["ssl"] = ssl_context
                connect_kwargs["server_hostname"] = self._host
            reader, writer = await asyncio.open_connection(
                self._host,
                self._port,
                **connect_kwargs,
            )
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


@dataclass
class _ServerTLSConfig:
    ssl_context: ssl.SSLContext
    temp_paths: list[str]


class Server:
    def __init__(self) -> None:
        self._handlers: dict[str, dict[str, UnaryUnaryRpcMethodHandler]] = {}
        self._server: Optional[asyncio.AbstractServer] = None
        self._host = "127.0.0.1"
        self._port = 0
        self._tls_config: Optional[_ServerTLSConfig] = None

    def add_generic_rpc_handlers(self, handlers: list[GenericRpcHandler]) -> None:
        for handler in handlers:
            self._handlers[handler.service_name] = handler.method_handlers

    def add_insecure_port(self, target: str) -> int:
        host, port = target.split(":")
        self._host = host
        self._port = int(port)
        self._tls_config = None
        return self._port

    def add_secure_port(self, target: str, credentials: "ServerCredentials") -> int:
        host, port = target.split(":")
        self._host = host
        self._port = int(port)
        self._tls_config = _create_server_tls_config(credentials)
        return self._port

    async def start(self) -> None:
        ssl_context = self._tls_config.ssl_context if self._tls_config else None
        self._server = await asyncio.start_server(
            self._handle_client,
            self._host,
            self._port,
            ssl=ssl_context,
        )
        if self._server.sockets:
            sockname = self._server.sockets[0].getsockname()
            if sockname and isinstance(sockname, tuple):
                self._port = int(sockname[1])

    async def wait_for_termination(self) -> None:
        if self._server is None:
            return
        async with self._server:
            await self._server.serve_forever()

    async def stop(self, grace: Optional[float]) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._tls_config:
            _cleanup_temp_paths(self._tls_config.temp_paths)
            self._tls_config = None

    @property
    def bound_port(self) -> int:
        if self._server and self._server.sockets:
            sockname = self._server.sockets[0].getsockname()
            if sockname and isinstance(sockname, tuple):
                return int(sockname[1])
        return self._port

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


@contextmanager
def _client_ssl_context(credentials: ChannelCredentials | None):
    if credentials is None:
        yield None
        return
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    if credentials.root_certificates:
        context.load_verify_locations(
            cadata=_ensure_text(credentials.root_certificates)
        )
    else:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    temp_paths: list[str] = []
    try:
        if credentials.certificate_chain and credentials.private_key:
            cert_path = _write_temp_file(credentials.certificate_chain)
            key_path = _write_temp_file(credentials.private_key)
            temp_paths.extend([cert_path, key_path])
            context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        yield context
    finally:
        _cleanup_temp_paths(temp_paths)


def _create_server_tls_config(credentials: "ServerCredentials") -> _ServerTLSConfig:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    temp_paths: list[str] = []
    key_path = _write_temp_file(credentials.private_key)
    cert_path = _write_temp_file(credentials.certificate_chain)
    temp_paths.extend([key_path, cert_path])
    try:
        context.load_cert_chain(certfile=cert_path, keyfile=key_path)
        if credentials.root_certificates:
            context.load_verify_locations(
                cadata=_ensure_text(credentials.root_certificates)
            )
        if credentials.require_client_auth:
            context.verify_mode = ssl.CERT_REQUIRED
    except Exception:
        _cleanup_temp_paths(temp_paths)
        raise
    return _ServerTLSConfig(ssl_context=context, temp_paths=temp_paths)


def _write_temp_file(data: bytes) -> str:
    fd, path = tempfile.mkstemp()
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    return path


def _cleanup_temp_paths(paths: Sequence[str]) -> None:
    for path in paths:
        try:
            os.remove(path)
        except FileNotFoundError:
            continue


def _ensure_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin1")


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
