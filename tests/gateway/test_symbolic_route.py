from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.gateway.app.routing.symbolic_router import router
from services.symbolic_engine.app.schemas import SymbolicResponse


class _StubSymbolicClient:
    async def solve(self, expr: str, subs: dict | None = None) -> SymbolicResponse:  # noqa: ANN001
        return SymbolicResponse(ok=True, result={"simplified": "x + 1", "cached": False}, error=None)


def create_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.symbolic_client = _StubSymbolicClient()
    return app


def test_symbolic_route_returns_expected_shape():
    app = create_app()
    client = TestClient(app)
    response = client.post("/v1/symbolic/solve", json={"expr": "x + 1", "subs": {"x": 2}})
    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["metadata"] == {"mode": "symbolic", "cache": False}
