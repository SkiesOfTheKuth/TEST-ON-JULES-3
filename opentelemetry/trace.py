"""Lightweight tracing primitives compatible with OpenTelemetry usage."""

from __future__ import annotations

import contextvars
import os
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence


_CURRENT_SPAN: contextvars.ContextVar[Span | None]
_CURRENT_SPAN = contextvars.ContextVar("opentelemetry_current_span", default=None)


class SpanKind:
    CLIENT = "client"
    SERVER = "server"


class StatusCode:
    OK = "OK"
    ERROR = "ERROR"


@dataclass
class Status:
    status_code: str
    description: str | None = None


class SpanContext:
    """Minimal span context storing trace/span identifiers and flags."""

    def __init__(
        self,
        trace_id: int,
        span_id: int,
        *,
        is_remote: bool = False,
        trace_flags: int = 0x01,
        tracestate: str | None = None,
    ) -> None:
        self.trace_id = trace_id
        self.span_id = span_id
        self.is_remote = is_remote
        self.trace_flags = trace_flags & 0xFF
        self.tracestate = tracestate

    @property
    def is_valid(self) -> bool:
        return bool(self.trace_id) and bool(self.span_id)

    @property
    def is_sampled(self) -> bool:
        return bool(self.trace_flags & 0x01)


@dataclass
class SpanEvent:
    name: str
    attributes: Dict[str, Any]
    timestamp: float


@dataclass
class SpanLink:
    context: SpanContext
    attributes: Dict[str, Any] | None = None


class _NoopSpan:
    """Span placeholder used when no span is active."""

    name = "noop"
    attributes: Dict[str, Any] = {}
    events: list[SpanEvent] = []
    status: Status | None = None
    parent: Span | None = None
    parent_span_id: int = 0
    span_id: int = 0
    trace_id: int = 0

    def set_attribute(self, *_: Any, **__: Any) -> None:  # noqa: D401
        return None

    def record_exception(self, *_: Any, **__: Any) -> None:  # noqa: D401
        return None

    def set_status(self, *_: Any, **__: Any) -> None:  # noqa: D401
        return None

    def add_event(self, *_: Any, **__: Any) -> None:  # noqa: D401
        return None

    def get_span_context(self) -> SpanContext:
        return SpanContext(0, 0)

    @property
    def context(self) -> SpanContext:
        return self.get_span_context()


class Span:
    """A lightweight span recording attributes and events."""

    def __init__(
        self,
        name: str,
        *,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Span | None = None,
        parent_context: SpanContext | None = None,
        processors: Iterable["SpanProcessor"] = (),
        links: Optional[Sequence[SpanContext]] = None,
        sampled: bool = True,
    ) -> None:
        self.name = name
        self.attributes: Dict[str, Any] = dict(attributes or {})
        self.parent = parent
        self.parent_span_id = 0
        self.status: Status | None = None
        self.events: list[SpanEvent] = []
        self.links: list[SpanLink] = [SpanLink(context=link) for link in links or []]

        if parent:
            trace_id = parent.context.trace_id
            parent_span_id = parent.context.span_id
            trace_flags = parent.context.trace_flags
            tracestate = parent.context.tracestate
        elif parent_context:
            trace_id = parent_context.trace_id
            parent_span_id = parent_context.span_id
            trace_flags = parent_context.trace_flags
            tracestate = parent_context.tracestate
        else:
            trace_id = secrets.randbits(128)
            parent_span_id = 0
            trace_flags = 0x01 if sampled else 0x00
            tracestate = None

        self.parent_span_id = parent_span_id
        span_id = secrets.randbits(64)
        self.trace_id = trace_id
        self.span_id = span_id
        self._sampled = sampled or bool(trace_flags & 0x01)
        self._context = SpanContext(
            trace_id,
            span_id,
            trace_flags=trace_flags if parent or parent_context else (0x01 if self._sampled else 0x00),
            tracestate=tracestate,
        )
        self._processors: List[SpanProcessor] = list(processors)
        self._ended = False

    def set_attribute(self, key: str, value: Any) -> None:
        if self._sampled:
            self.attributes[key] = value

    def record_exception(self, exc: BaseException) -> None:
        if not self._sampled:
            return
        self.events.append(
            SpanEvent(
                name="exception",
                attributes={
                    "exception.type": type(exc).__name__,
                    "exception.message": str(exc),
                },
                timestamp=time.time(),
            )
        )

    def set_status(self, status: Status) -> None:
        if self._sampled:
            self.status = status

    def add_event(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> None:
        if not self._sampled:
            return
        self.events.append(
            SpanEvent(name=name, attributes=dict(attributes or {}), timestamp=time.time())
        )

    def end(self) -> None:
        if self._ended:
            return
        self._ended = True
        if not self._sampled:
            return
        for processor in list(self._processors):
            processor.on_end(self)

    def get_span_context(self) -> SpanContext:
        return self._context

    @property
    def context(self) -> SpanContext:
        return self._context


class SpanProcessor:
    """Base processor receiving lifecycle notifications."""

    def on_start(self, span: Span) -> None:  # pragma: no cover - default no-op
        return None

    def on_end(self, span: Span) -> None:  # pragma: no cover - default no-op
        return None

    def shutdown(self) -> None:  # pragma: no cover - default no-op
        return None

    def force_flush(self) -> None:  # pragma: no cover - default no-op
        return None


class Tracer:
    """Create spans associated with a tracer provider."""

    def __init__(self, provider: "TracerProvider", instrumentation_name: str) -> None:
        self._provider = provider
        self._instrumentation_name = instrumentation_name

    @contextmanager
    def start_as_current_span(
        self,
        name: str,
        *,
        attributes: Optional[Dict[str, Any]] = None,
        parent: Span | SpanContext | None = None,
        links: Optional[Sequence[SpanContext]] = None,
    ) -> Span:
        current_parent = get_current_span()
        parent_span = None if isinstance(current_parent, _NoopSpan) else current_parent
        parent_context: SpanContext | None = None

        if isinstance(parent, Span):
            parent_span = parent
            parent_context = parent.get_span_context()
        elif isinstance(parent, SpanContext):
            parent_span = None
            parent_context = parent
        elif isinstance(parent, _NoopSpan):
            parent_span = None
            parent_context = None

        if parent_span is None and parent_context is None and not isinstance(current_parent, _NoopSpan):
            parent_context = current_parent.get_span_context()

        sampled = self._provider._should_sample(parent_context)
        span = Span(
            name,
            attributes=attributes,
            parent=parent_span,
            parent_context=parent_context,
            processors=self._provider._processors,
            links=links,
            sampled=sampled,
        )
        if sampled:
            for processor in self._provider._processors:
                processor.on_start(span)
        token = _CURRENT_SPAN.set(span)
        try:
            yield span
        finally:
            _CURRENT_SPAN.reset(token)
            span.end()


class TracerProvider:
    """Holds span processors and manufactures tracers."""

    def __init__(self) -> None:
        self._processors: List[SpanProcessor] = []
        sampler = os.getenv("OTEL_TRACES_SAMPLER", "parentbased_always_on").lower()
        self._sampler = sampler
        self._sampler_arg = os.getenv("OTEL_TRACES_SAMPLER_ARG")

    def get_tracer(self, instrumentation_name: str) -> Tracer:
        return Tracer(self, instrumentation_name)

    def add_span_processor(self, processor: SpanProcessor) -> None:
        self._processors.append(processor)

    def shutdown(self) -> None:  # pragma: no cover - compatibility
        for processor in self._processors:
            processor.shutdown()

    def _should_sample(self, parent_context: SpanContext | None) -> bool:
        sampler = self._sampler
        if sampler in {"always_off", "alwaysoff"}:
            return False
        if sampler in {"always_on", "alwayson"}:
            return True
        if sampler in {"parentbased_always_off", "parentbased_alwaysoff"}:
            if parent_context is not None:
                return parent_context.is_sampled
            return False
        # Default parent-based always on behaviour.
        if parent_context is not None and not parent_context.is_sampled:
            return False
        return True


_TRACER_PROVIDER: TracerProvider = TracerProvider()


def set_tracer_provider(provider: TracerProvider) -> None:
    global _TRACER_PROVIDER
    _TRACER_PROVIDER = provider


def get_tracer_provider() -> TracerProvider:
    return _TRACER_PROVIDER


def get_tracer(instrumentation_name: str | None = None) -> Tracer:
    name = instrumentation_name or "default"
    return _TRACER_PROVIDER.get_tracer(name)


def get_current_span() -> Span:
    span = _CURRENT_SPAN.get()
    return span if span is not None else _NoopSpan()


Span = Span


__all__ = [
    "Span",
    "SpanContext",
    "SpanEvent",
    "SpanKind",
    "SpanLink",
    "Status",
    "StatusCode",
    "Tracer",
    "TracerProvider",
    "get_current_span",
    "get_tracer",
    "get_tracer_provider",
    "set_tracer_provider",
    "SpanProcessor",
]
