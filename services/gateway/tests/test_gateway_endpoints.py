import sys
import importlib
import types
from pathlib import Path
import asyncio
from types import SimpleNamespace

import pytest
import pytest_asyncio
from starlette import status

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.protos import evaluator_pb2


class StubRateLimiter:
    def __init__(self, *args, **kwargs):
        self.allowed = True
        self.calls: list[str] = []

    async def allow(self, key: str) -> bool:
        self.calls.append(key)
        return self.allowed


class StubRedis:
    def __init__(self):
        self.storage: dict[str, float] = {}

    @classmethod
    def from_url(cls, url: str, decode_responses: bool = True) -> "StubRedis":
        return cls()

    async def close(self) -> None:  # pragma: no cover - stub cleanup
        return None


class StubCache:
    def __init__(self):
        self.storage: dict[str, float] = {}

    async def get(self, key: str):
        return self.storage.get(key)

    async def set(self, key: str, value: float):
        self.storage[key] = value


class StubEvaluatorStub:
    def __init__(self):
        self.calls: list[str] = []
        self.response = evaluator_pb2.EvaluateResponse(value=3.0, duration_ms=4.0)

    async def Evaluate(self, request, timeout=None, metadata=None):
        self.calls.append(request.expression)
        return self.response


class StubChannel:
    async def close(self) -> None:  # pragma: no cover - stub cleanup
        return None


class StubSession:
    def __init__(self):
        self.added = []

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        return None


async def fake_get_session():
    yield StubSession()


@pytest_asyncio.fixture
async def gateway_test_context(monkeypatch):
    for module in list(sys.modules):
        if module == "app" or module.startswith("app."):
            del sys.modules[module]

    stub_instrumentation = types.ModuleType("app.instrumentation")
    stub_instrumentation.configure_logging = lambda settings: None
    stub_instrumentation.configure_tracing = lambda settings: None
    stub_instrumentation.instrument_app = lambda app, settings: None
    stub_instrumentation.record_rate_limit_rejection = lambda reason: None
    sys.modules["app.instrumentation"] = stub_instrumentation

    main = importlib.import_module("app.main")
    schemas = importlib.import_module("app.schemas")
    security = importlib.import_module("app.security")

    monkeypatch.setattr(main, "RateLimiter", StubRateLimiter)
    monkeypatch.setattr(main, "Redis", StubRedis)

    async def fake_init_db(settings):
        return None

    monkeypatch.setattr(main, "init_db", fake_init_db)

    stub_evaluator = StubEvaluatorStub()
    monkeypatch.setattr(main, "_create_grpc_channel", lambda settings: StubChannel())
    monkeypatch.setattr(main.evaluator_pb2_grpc, "EvaluatorStub", lambda channel: stub_evaluator)

    recorded_audits = []

    async def fake_persist_audit(*args, **kwargs):
        recorded_audits.append({"args": args, "kwargs": kwargs})

    async def fake_consume_quota(session, api_key_id, config):
        if fake_consume_quota.should_raise:
            raise main.QuotaExceededError("quota exceeded")

    fake_consume_quota.should_raise = False

    monkeypatch.setattr(main, "_persist_audit", fake_persist_audit)
    monkeypatch.setattr(main, "consume_quota", fake_consume_quota)
    monkeypatch.setattr(main, "get_session", fake_get_session)

    app = main.app
    app.dependency_overrides.clear()

    async def override_require_api_key(request):
        key = request.headers.get("X-Api-Key")
        if not key:
            raise main.HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
        if key != "valid-key":
            raise main.HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        return security.AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key=key)

    app.dependency_overrides[main.require_api_key] = override_require_api_key

    app.state.redis = StubRedis.from_url("redis://test")
    app.state.cache = StubCache()
    app.state.rate_limit_key = StubRateLimiter()
    app.state.rate_limit_ip = StubRateLimiter()
    app.state.quota_config = main.QuotaConfig(limit=main.settings.quota.limit, window_seconds=main.settings.quota.window_seconds)
    app.state.grpc_channel = StubChannel()
    app.state.grpc_stub = stub_evaluator

    yield {
        "main": main,
        "schemas": schemas,
        "security": security,
        "app": app,
        "evaluator": stub_evaluator,
        "rate_limiter_key": app.state.rate_limit_key,
        "rate_limiter_ip": app.state.rate_limit_ip,
        "recorded_audits": recorded_audits,
        "consume_quota": fake_consume_quota,
    }

    recorded_audits.clear()
    app.dependency_overrides.clear()
    sys.modules.pop("app.instrumentation", None)


def _make_request(host="127.0.0.1"):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/calculate",
        "headers": [],
        "client": (host, 1234),
    }
    from starlette.requests import Request

    return Request(scope, receive=lambda: None)


@pytest.mark.asyncio
async def test_calculate_success_invokes_evaluator(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    ExpressionRequest = ctx["schemas"].ExpressionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    payload = ExpressionRequest(expression="1+2")
    request = _make_request()
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    response = await main.calculate_sync(payload, request, api_key=api_key, session=session)

    assert response.value == pytest.approx(3.0)
    assert response.from_cache is False
    assert len(ctx["evaluator"].calls) == 1
    await asyncio.sleep(0)
    assert ctx["recorded_audits"], "audit log should capture success"


@pytest.mark.asyncio
async def test_calculate_uses_cache_on_repeated_calls(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    ExpressionRequest = ctx["schemas"].ExpressionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    payload = ExpressionRequest(expression="2*3")
    request = _make_request()
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    first = await main.calculate_sync(payload, request, api_key=api_key, session=session)
    assert first.from_cache is False
    second = await main.calculate_sync(payload, request, api_key=api_key, session=session)
    assert second.from_cache is True
    assert len(ctx["evaluator"].calls) == 1


@pytest.mark.asyncio
async def test_rate_limit_rejection_returns_http_429(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    ExpressionRequest = ctx["schemas"].ExpressionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    ctx["rate_limiter_key"].allowed = False
    payload = ExpressionRequest(expression="5-3")
    request = _make_request()
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    with pytest.raises(main.HTTPException) as exc:
        await main.calculate_sync(payload, request, api_key=api_key, session=session)

    assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_quota_exceeded_returns_http_429(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    ExpressionRequest = ctx["schemas"].ExpressionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    ctx["consume_quota"].should_raise = True
    payload = ExpressionRequest(expression="8/2")
    request = _make_request()
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    with pytest.raises(main.HTTPException) as exc:
        await main.calculate_sync(payload, request, api_key=api_key, session=session)

    assert exc.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.asyncio
async def test_require_api_key_missing_header_raises_401(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]

    scope = {"type": "http", "method": "POST", "path": "/calculate", "headers": [], "client": ("127.0.0.1", 1234)}
    from starlette.requests import Request

    request = Request(scope, receive=lambda: None)

    with pytest.raises(main.HTTPException) as exc:
        await main.require_api_key(request, session=StubSession())

    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
