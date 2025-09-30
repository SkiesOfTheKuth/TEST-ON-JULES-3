"""Integration tests for the Flask API."""

from __future__ import annotations

import pytest

AUTH_HEADERS = {"Authorization": "Bearer test-token"}


def test_calculate_success(client) -> None:
    response = client.post("/calculate", json={"expression": "1 + 2"}, headers=AUTH_HEADERS)

    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert body["result"] == pytest.approx(3.0)


def test_calculate_validation_error(client) -> None:
    response = client.post("/calculate", json={"expression": ""}, headers=AUTH_HEADERS)

    assert response.status_code == 400
    body = response.get_json()
    assert body is not None
    assert "error" in body


def test_calculate_rejects_disallowed_function(client) -> None:
    response = client.post(
        "/calculate",
        json={"expression": "__import__('os').system('echo hello')"},
        headers=AUTH_HEADERS,
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body is not None
    assert "unsupported" in body["error"].lower()


def test_calculate_requires_authorization(client) -> None:
    response = client.post("/calculate", json={"expression": "1 + 1"})

    assert response.status_code == 401
    body = response.get_json()
    assert body == {"error": "Unauthorized"}


def test_calculate_enforces_rate_limit(app, client) -> None:
    original_limit = app.config["RATE_LIMIT"]
    app.config["RATE_LIMIT"] = "1 per minute"

    try:
        first = client.post(
            "/calculate",
            json={"expression": "1 + 1"},
            headers=AUTH_HEADERS,
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        )
        assert first.status_code == 200

        second = client.post(
            "/calculate",
            json={"expression": "1 + 2"},
            headers=AUTH_HEADERS,
            environ_base={"REMOTE_ADDR": "10.0.0.1"},
        )

        assert second.status_code == 429
        body = second.get_json()
        assert body is not None
        assert body["error"] == "Rate limit exceeded"
    finally:
        app.config["RATE_LIMIT"] = original_limit

