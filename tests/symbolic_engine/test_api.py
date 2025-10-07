from fastapi.testclient import TestClient

from services.symbolic_engine.app import cache
from services.symbolic_engine.app.main import app


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    def get(self, key: str):
        return self._store.get(key)

    def setex(self, key: str, ttl: int, value: str) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)


client = TestClient(app)


def setup_module(module):  # noqa: ANN001
    fake = _FakeRedis()
    cache._redis_client = fake  # type: ignore[attr-defined]


def test_symbolic_endpoint_returns_payload():
    response = client.post("/v1/symbolic", json={"expr": "x + 1", "subs": {"x": 2}})
    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["result"]["cached"] is False

    repeat = client.post("/v1/symbolic", json={"expr": "x + 1", "subs": {"x": 2}})
    cached_payload = repeat.json()
    assert cached_payload["result"]["cached"] is True
