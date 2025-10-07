from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_compute_endpoint_simplify():
    payload = {
        "operation": "simplify",
        "expression": "x**2 + 2*x + 1",
    }
    resp = client.post("/symbolic/compute", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"]["canonical"] == "(x + 1)**2"
    assert body["metadata"]["execution_ms"] >= 0


def test_compute_endpoint_invalid_expression():
    payload = {
        "operation": "simplify",
        "expression": "import os",
    }
    resp = client.post("/symbolic/compute", json=payload)
    assert resp.status_code == 400
    assert "Failed to parse expression" in resp.json()["detail"]
