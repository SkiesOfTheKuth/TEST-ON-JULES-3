from fastapi.testclient import TestClient

from services.symbolic_engine.app.main import app


client = TestClient(app)


def test_simplify_endpoint_returns_canonical_form():
    response = client.post(
        "/v1/simplify",
        json={"expression": "x + x", "variables": ["x"], "canonicalize": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == "2*x"
    assert "sandbox" in data["metadata"]
    assert data["canonical_form"] is not None


def test_sandbox_guard_error_response():
    response = client.post(
        "/v1/simplify",
        json={"expression": "__import__('os')", "variables": []},
    )
    assert response.status_code == 400
    data = response.json()
    assert "detail" in data
    assert data["diagnostics"]["memory_limit_mb"] > 0
