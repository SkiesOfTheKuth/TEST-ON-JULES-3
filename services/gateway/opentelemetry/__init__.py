"""Small subset of the OpenTelemetry API used in tests."""

from __future__ import annotations

from .trace import get_tracer

__all__ = ["trace", "get_tracer"]


class _TraceModule:
    get_tracer = staticmethod(get_tracer)


trace = _TraceModule()
