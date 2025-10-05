"""Minimal span exporter/processor shims for tests."""

from __future__ import annotations

from typing import Iterable, List

from opentelemetry.trace import Span, SpanProcessor


class SpanExporter:
    """Base exporter API compatible with OpenTelemetry."""

    def export(self, spans: Iterable[Span]) -> None:  # pragma: no cover - default no-op
        return None

    def shutdown(self) -> None:  # pragma: no cover - default no-op
        return None


class SimpleSpanProcessor(SpanProcessor):
    """Immediately forwards finished spans to the exporter."""

    def __init__(self, exporter: SpanExporter) -> None:
        self._exporter = exporter

    def on_end(self, span: Span) -> None:  # noqa: D401
        self._exporter.export([span])

    def shutdown(self) -> None:  # noqa: D401
        self._exporter.shutdown()


class BatchSpanProcessor(SimpleSpanProcessor):
    """Alias for tests; behaves like the simple processor."""


class ConsoleSpanExporter(SpanExporter):
    """No-op exporter placeholder for console output."""

    def export(self, spans: Iterable[Span]) -> None:  # noqa: D401 - compatibility
        for _ in spans:
            pass


class InMemorySpanExporter(SpanExporter):
    """Collects spans in memory for inspection during tests."""

    def __init__(self) -> None:
        self._finished_spans: List[Span] = []

    def export(self, spans: Iterable[Span]) -> None:  # noqa: D401
        self._finished_spans.extend(spans)

    def get_finished_spans(self) -> List[Span]:
        return list(self._finished_spans)

    def clear(self) -> None:
        self._finished_spans.clear()


__all__ = [
    "BatchSpanProcessor",
    "ConsoleSpanExporter",
    "InMemorySpanExporter",
    "SimpleSpanProcessor",
    "SpanExporter",
]
