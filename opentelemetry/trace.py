"""Trace primitives for the OpenTelemetry test shim."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Optional


class SpanKind:
    CLIENT = "client"
    SERVER = "server"


class StatusCode:
    OK = "OK"
    ERROR = "ERROR"


class Status:
    def __init__(self, status_code: str, description: str | None = None) -> None:
        self.status_code = status_code
        self.description = description


class _Span:
    def __init__(self) -> None:
        self.attributes: Dict[str, Any] = {}
        self.status: Optional[Status] = None
        self.events: list[tuple[str, Dict[str, Any]]] = []

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:  # pragma: no cover - compatibility
        self.attributes.setdefault("exceptions", []).append(str(exc))

    def set_status(self, status: Status) -> None:
        self.status = status

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.events.append((name, attributes or {}))


@contextmanager
def start_as_current_span(*args, **kwargs):  # noqa: ARG002 - compatibility shim
    span = _Span()
    yield span


class _Tracer:
    def start_as_current_span(self, *args, **kwargs):  # noqa: ARG002 - compatibility
        return start_as_current_span()


def get_tracer(name: str | None = None) -> _Tracer:  # noqa: ARG002 - parity with real API
    return _Tracer()


Span = _Span


__all__ = [
    "Span",
    "SpanKind",
    "Status",
    "StatusCode",
    "get_tracer",
]
