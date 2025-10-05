"""Minimal tracing helpers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Iterator


class StatusCode(Enum):
    OK = "OK"
    ERROR = "ERROR"


@dataclass
class Status:
    status_code: StatusCode


class SpanKind(Enum):
    INTERNAL = "INTERNAL"
    SERVER = "SERVER"
    CLIENT = "CLIENT"


class _Span:
    def __init__(self, name: str, attributes: Dict[str, Any] | None = None) -> None:
        self.name = name
        self.attributes = attributes or {}
        self.status: Status | None = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def set_status(self, status: Status) -> None:
        self.status = status

    def record_exception(self, exc: BaseException) -> None:  # pragma: no cover - diagnostic only
        self.attributes.setdefault("exceptions", []).append(str(exc))

    def __enter__(self) -> "_Span":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class _Tracer:
    def start_as_current_span(self, name: str, attributes: Dict[str, Any] | None = None) -> _Span:
        return _Span(name, attributes)


def get_tracer(name: str) -> _Tracer:
    return _Tracer()
