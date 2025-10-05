from __future__ import annotations

from collections import Counter

import pytest
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanContext

from src.observability.metrics import get_job_metrics

from tests.observability.test_spans_job_flow import (
    _assert_no_pii,
    _install_tracing,
    _short_id,
)


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

    with gateway_instr.start_ws_span("connect", job_id, link_from=link_context):
        pass
    with gateway_instr.start_ws_span("hydrate", job_id, link_from=link_context):
        pass
    with gateway_instr.start_ws_span("stream", job_id, link_from=link_context):
        pass

    spans = exporter.get_finished_spans()
    counts = Counter(span.name for span in spans)
    assert counts["ws.connect"] == 1
    assert counts["ws.hydrate"] == 1
    assert counts["ws.stream"] == 1

    ws_spans = {span.name: span for span in spans}

    for name in ("ws.connect", "ws.hydrate", "ws.stream"):
        span = ws_spans[name]
        assert len(span.links) == 1
        link = span.links[0]
        assert link.context.trace_id == enqueue_context.trace_id
        assert link.context.span_id == enqueue_context.span_id

    for span in spans:
        assert set(span.attributes.keys()) == {"job_id_short"}
        assert span.attributes["job_id_short"] == _short_id(job_id)
        assert len(span.attributes["job_id_short"]) <= 16
        assert span.attributes["job_id_short"] != job_id
        _assert_no_pii(span.attributes, job_id)

    exporter.clear()

    with pytest.raises(ValueError):
        with gateway_instr.start_ws_span("invalid", job_id):
            pass
