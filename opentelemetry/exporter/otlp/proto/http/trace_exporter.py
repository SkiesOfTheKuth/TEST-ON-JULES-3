"""Stub OTLP exporter for local testing."""

from __future__ import annotations

from typing import Iterable

from opentelemetry.trace import Span


class OTLPSpanExporter:
    """Placeholder OTLP exporter that drops spans."""

    def __init__(self, *args, **kwargs) -> None:  # noqa: D401 - compatibility
        return None

    def export(self, spans: Iterable[Span]) -> None:  # noqa: D401 - drop spans
        for _ in spans:
            pass

    def shutdown(self) -> None:  # noqa: D401
        return None


__all__ = ["OTLPSpanExporter"]
