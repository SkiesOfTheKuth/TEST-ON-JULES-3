"""Propagation helpers for the OpenTelemetry shim."""

from __future__ import annotations

from typing import Any, Dict, MutableMapping, Optional

from . import trace
from .trace import SpanContext

_TRACEPARENT_HEADER = "traceparent"
_TRACESTATE_HEADER = "tracestate"


def _normalize_key(key: str) -> str:
    return key.lower()


def inject(carrier: MutableMapping[str, Any]) -> None:  # noqa: D401 - compatibility
    """Inject the active span context into the provided carrier."""

    if carrier is None:
        return

    span = trace.get_current_span()
    if span is None:
        return

    context = span.get_span_context()
    if not context or not context.is_valid:
        return

    trace_id = f"{context.trace_id:032x}"
    span_id = f"{context.span_id:016x}"
    trace_flags = context.trace_flags & 0xFF
    header_value = f"00-{trace_id}-{span_id}-{trace_flags:02x}"
    carrier[_TRACEPARENT_HEADER] = header_value

    if context.tracestate:
        carrier[_TRACESTATE_HEADER] = context.tracestate


def extract(carrier: Optional[MutableMapping[str, Any]]) -> SpanContext | None:  # noqa: D401 - compatibility
    """Extract a :class:`SpanContext` from the provided carrier."""

    if not carrier:
        return None

    traceparent_value: str | None = None
    tracestate_value: str | None = None
    for key, value in carrier.items():
        lowered = _normalize_key(str(key))
        if lowered == _TRACEPARENT_HEADER and value:
            traceparent_value = str(value)
        elif lowered == _TRACESTATE_HEADER and value:
            tracestate_value = str(value)

    if not traceparent_value:
        return None

    parts = traceparent_value.split("-")
    if len(parts) != 4:
        return None

    _, trace_id_hex, span_id_hex, trace_flags_hex = parts
    try:
        trace_id = int(trace_id_hex, 16)
        span_id = int(span_id_hex, 16)
        trace_flags = int(trace_flags_hex, 16)
    except (TypeError, ValueError):
        return None

    if not trace_id or not span_id:
        return None

    return SpanContext(
        trace_id,
        span_id,
        is_remote=True,
        trace_flags=trace_flags,
        tracestate=tracestate_value,
    )


__all__ = ["inject", "extract"]
