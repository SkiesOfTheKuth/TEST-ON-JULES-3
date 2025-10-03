"""Observability and health endpoint tests."""

from __future__ import annotations

from unittest import mock

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def test_health_endpoints(client) -> None:
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.get_json() == {"status": "ok"}

    ready = client.get("/readyz")
    assert ready.status_code == 200
    assert ready.get_json() == {"status": "ready"}


def test_metrics_endpoint(client) -> None:
    client.post("/calculate", json={"expression": "1 + 2"}, headers=AUTH_HEADERS)

    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.content_type == "text/plain; version=0.0.4; charset=utf-8"
    body = response.data.decode()
    assert "calculator_http_requests_total" in body
    assert "calculator_http_request_duration_seconds" in body
    assert "calculator_evaluations_total" in body


def test_ready_endpoint_reports_failure(app, client, monkeypatch) -> None:
    evaluator = app.extensions["calculator_evaluator"]
    monkeypatch.setattr(
        type(evaluator), "health_check", mock.Mock(side_effect=RuntimeError("boom"))
    )

    ready = client.get("/readyz")
    assert ready.status_code == 503
    assert ready.get_json() == {"status": "unavailable"}


def test_static_assets_are_cached(client) -> None:
    response = client.get("/static/style.css")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "public, max-age=31536000, immutable"
