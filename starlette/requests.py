"""Minimal Starlette request object for tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict


class Request:
    def __init__(self, scope: Dict[str, Any], receive: Callable[[], Awaitable[Any]] | None = None) -> None:
        self.scope = scope
        headers = scope.get("headers") or []
        self.headers = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in headers}
        client = scope.get("client")
        self.client = SimpleNamespace(host=client[0], port=client[1]) if client else None
        self.state = SimpleNamespace()


__all__ = ["Request"]
