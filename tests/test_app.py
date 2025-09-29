"""Integration tests for the Flask API."""

from __future__ import annotations

import pytest


def test_calculate_success(client) -> None:
    response = client.post("/calculate", json={"expression": "1 + 2"})

    assert response.status_code == 200
    body = response.get_json()
    assert body is not None
    assert body["result"] == pytest.approx(3.0)


def test_calculate_validation_error(client) -> None:
    response = client.post("/calculate", json={"expression": ""})

    assert response.status_code == 400
    body = response.get_json()
    assert body is not None
    assert "error" in body


def test_calculate_rejects_disallowed_function(client) -> None:
    response = client.post(
        "/calculate",
        json={"expression": "__import__('os').system('echo hello')"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body is not None
    assert "unsupported" in body["error"].lower()

