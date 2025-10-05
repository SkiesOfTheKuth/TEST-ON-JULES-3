"""Extremely small FastAPI stand-in for offline tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Dict

__all__ = ["FastAPI", "HTTPException", "Depends", "Request", "status"]


class HTTPException(Exception):
    def __init__(self, status_code: int, detail: str | None = None) -> None:
        super().__init__(detail or "HTTP error")
        self.status_code = status_code
        self.detail = detail


class _Status:
    HTTP_200_OK = 200
    HTTP_202_ACCEPTED = 202
    HTTP_401_UNAUTHORIZED = 401
    HTTP_404_NOT_FOUND = 404
    HTTP_429_TOO_MANY_REQUESTS = 429
    HTTP_503_SERVICE_UNAVAILABLE = 503
    HTTP_500_INTERNAL_SERVER_ERROR = 500


status = _Status()


class Depends:
    def __init__(self, dependency: Callable[..., Any]) -> None:
        self.dependency = dependency


class Request:
    def __init__(self, headers: Dict[str, str] | None = None, client: tuple[str, int] | None = None) -> None:
        self.headers = headers or {}
        self.client = SimpleNamespace(host=client[0], port=client[1]) if client else None
        self.state = SimpleNamespace()


class FastAPI:
    def __init__(self, title: str | None = None, version: str | None = None) -> None:
        self.title = title
        self.version = version
        self.dependency_overrides: Dict[Callable[..., Any], Callable[..., Any]] = {}
        self.state = SimpleNamespace()
        self._events: Dict[str, list[Callable[..., Any]]] = {"startup": [], "shutdown": []}

    def on_event(self, event: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._events.setdefault(event, []).append(func)
            return func

        return decorator

    def post(self, path: str, response_model: Any | None = None, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda func: func

    def get(self, path: str, response_model: Any | None = None, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda func: func

    def delete(self, path: str, **kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        return lambda func: func
