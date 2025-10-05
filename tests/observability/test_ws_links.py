from __future__ import annotations

from collections import Counter

import pytest

from tests.observability.test_spans_job_flow import (
    _assert_no_pii,
    _install_tracing,
    _restore_otel_modules,
    _short_id,
)

_restore_otel_modules()

from opentelemetry.propagate import extract
from opentelemetry.trace import SpanContext

from src.observability.metrics import get_job_metrics


def test_websocket_span_links_enqueue_context() -> None:
    exporter, gateway_instr, _ = _install_tracing()
    metrics = get_job_metrics(None)

    job_id = "99aa88bb-ccdd-eeff-0011-223344556677"

    with gateway_instr.start_enqueue_span(job_id, "calculator", "gateway.execute_job") as enqueue_span:
        headers = gateway_instr.prepare_enqueue_headers(metrics, "calculator", "gateway.execute_job")
        enqueue_context = enqueue_span.get_span_context()

    link_context = extract(headers)
    assert isinstance(link_context, SpanContext)

    exporter.clear()

    with gateway_instr.start_ws_span("connect", job_id, link_from=link_context) as connect_span:
        _assert_link(connect_span, enqueue_context)
    with gateway_instr.start_ws_span("hydrate", job_id, link_from=link_context) as hydrate_span:
        _assert_link(hydrate_span, enqueue_context)
    with gateway_instr.start_ws_span("stream", job_id, link_from=link_context) as stream_span:
        _assert_link(stream_span, enqueue_context)

    spans = exporter.get_finished_spans()
    counts = Counter(span.name for span in spans)
    assert counts["ws.connect"] == 1
    assert counts["ws.hydrate"] == 1
    assert counts["ws.stream"] == 1

    ws_spans = {span.name: span for span in spans}

    for name in ("ws.connect", "ws.hydrate", "ws.stream"):
        span = ws_spans[name]
        _assert_link(span, enqueue_context)

    for span in spans:
        assert span.attributes["job_id_short"] == _short_id(job_id)
        assert len(span.attributes["job_id_short"]) <= 16
        assert span.attributes["job_id_short"] != job_id
        _assert_no_pii(span.attributes, job_id)

    exporter.clear()

    with pytest.raises(ValueError):
        with gateway_instr.start_ws_span("invalid", job_id):
            pass
def _assert_link(span, enqueue_context):
    if span.links:
        link = span.links[0]
        assert link.context.trace_id == enqueue_context.trace_id
        assert link.context.span_id == enqueue_context.span_id
    else:
        assert span.attributes["ws.link.trace_id"] == enqueue_context.trace_id
        assert span.attributes["ws.link.span_id"] == enqueue_context.span_id

