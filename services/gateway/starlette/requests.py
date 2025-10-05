"""Simplified Request object compatible with FastAPI stub."""

from __future__ import annotations

from typing import Any, Callable
from types import SimpleNamespace


class Request:
    def __init__(self, scope: dict[str, Any], receive: Callable[[], Any] | None = None) -> None:
        headers = scope.get("headers", [])
        self.headers = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in headers}
        client = scope.get("client")
        self.client = SimpleNamespace(host=client[0], port=client[1]) if client else None
        self.state = SimpleNamespace()
