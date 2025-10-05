"""Lightweight FastAPI compatibility shim for unit tests."""

from __future__ import annotations

from http import HTTPStatus
from types import SimpleNamespace
from typing import Any, Callable, Dict


class Depends:
    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: Any = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class Request:
    def __init__(self, headers: Dict[str, str] | None = None, client: Any | None = None) -> None:
        self.headers = headers or {}
        self.client = SimpleNamespace(host=client[0], port=client[1]) if client else None
        self.state = SimpleNamespace()


class WebSocket:
    def __init__(self, headers: Dict[str, str] | None = None) -> None:
        self.headers = headers or {}

    async def accept(self) -> None:  # pragma: no cover - compatibility
        return None

    async def send_json(self, data: Any) -> None:  # pragma: no cover - compatibility
        return None

    async def close(self, code: int, reason: str | None = None) -> None:  # pragma: no cover - compatibility
        return None


class WebSocketDisconnect(Exception):
    pass


class FastAPI:
    def __init__(self, title: str = "FastAPI", version: str = "0.1.0") -> None:
        self.title = title
        self.version = version
        self.state = SimpleNamespace()
        self.routes: list[tuple[str, Callable[..., Any]]] = []
        self.websocket_routes: list[tuple[str, Callable[..., Any]]] = []
        self._events: Dict[str, list[Callable[..., Any]]] = {"startup": [], "shutdown": []}
        self.dependency_overrides: Dict[Any, Any] = {}

    def post(self, path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes.append((path, func))
            return func

        return decorator

    def get(self, path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.routes.append((path, func))
            return func

        return decorator

    def websocket(self, path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.websocket_routes.append((path, func))
            return func

        return decorator

    def on_event(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._events.setdefault(event, []).append(func)
            return func

        return decorator


class _StatusModule:
    HTTP_200_OK = HTTPStatus.OK
    HTTP_202_ACCEPTED = HTTPStatus.ACCEPTED
    HTTP_401_UNAUTHORIZED = HTTPStatus.UNAUTHORIZED
    HTTP_404_NOT_FOUND = HTTPStatus.NOT_FOUND
    HTTP_429_TOO_MANY_REQUESTS = HTTPStatus.TOO_MANY_REQUESTS
    HTTP_503_SERVICE_UNAVAILABLE = HTTPStatus.SERVICE_UNAVAILABLE
    WS_1008_POLICY_VIOLATION = 1008
    WS_1011_INTERNAL_ERROR = 1011


status = _StatusModule()


__all__ = [
    "Depends",
    "FastAPI",
    "HTTPException",
    "Request",
    "WebSocket",
    "WebSocketDisconnect",
    "status",
]
