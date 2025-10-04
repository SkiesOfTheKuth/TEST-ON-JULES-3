import sys
import importlib
import types
from pathlib import Path
import asyncio
import datetime as dt
from types import SimpleNamespace

import pytest
from http import HTTPStatus

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_ROOT = Path(__file__).resolve().parents[1]
for candidate in (GATEWAY_ROOT, REPO_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

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


class StubJobCache:
    def __init__(self):
        self.storage: dict[str, dict] = {}

    async def get(self, job_id: str):
        return self.storage.get(job_id)

    async def set(self, job_id: str, payload: dict):
        self.storage[job_id] = payload


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


@pytest.fixture
def gateway_test_context(monkeypatch):
    for module in list(sys.modules):
        if module == "app" or module.startswith("app."):
            del sys.modules[module]

    stub_instrumentation = types.ModuleType("app.instrumentation")
    stub_instrumentation.configure_logging = lambda settings: None
    stub_instrumentation.configure_tracing = lambda settings: None
    stub_instrumentation.instrument_app = lambda app, settings: None
    stub_instrumentation.record_rate_limit_rejection = lambda reason: None
    sys.modules["app.instrumentation"] = stub_instrumentation

    stub_opentelemetry = types.ModuleType("opentelemetry")

    class _StubSpan:
        def __init__(self):
            self.attributes = {}

        def set_attribute(self, key, value):
            self.attributes[key] = value

        def record_exception(self, exc):
            return None

        def set_status(self, status):
            return None

    class _SpanContextManager:
        def __init__(self, *args, **kwargs):
            self.span = _StubSpan()

        def __enter__(self):
            return self.span

        def __exit__(self, exc_type, exc, tb):
            return False

    class _StubTracer:
        def start_as_current_span(self, *args, **kwargs):
            return _SpanContextManager()

    stub_trace = types.ModuleType("opentelemetry.trace")
    stub_trace.get_tracer = lambda name=None: _StubTracer()
    stub_trace.SpanKind = types.SimpleNamespace(CLIENT="client", SERVER="server")

    class _StubStatus:
        def __init__(self, code, description=None):
            self.code = code
            self.description = description

    class _StubStatusCode:
        OK = "OK"
        ERROR = "ERROR"

    stub_trace.Status = _StubStatus
    stub_trace.StatusCode = _StubStatusCode

    stub_propagate = types.ModuleType("opentelemetry.propagate")
    stub_propagate.inject = lambda carrier: None
    stub_propagate.extract = lambda carrier: {}

    stub_context = types.ModuleType("opentelemetry.context")
    stub_context.attach = lambda context: context
    stub_context.detach = lambda token: None

    stub_opentelemetry.trace = stub_trace
    stub_opentelemetry.propagate = stub_propagate
    stub_opentelemetry.context = stub_context

    sys.modules["opentelemetry"] = stub_opentelemetry
    sys.modules["opentelemetry.trace"] = stub_trace
    sys.modules["opentelemetry.propagate"] = stub_propagate
    sys.modules["opentelemetry.context"] = stub_context

    main = importlib.import_module("app.main")
    schemas = importlib.import_module("app.schemas")
    security = importlib.import_module("app.security")

    monkeypatch.setattr(main, "RateLimiter", StubRateLimiter)
    monkeypatch.setattr(main, "Redis", StubRedis)

    async def fake_init_db(settings):
        return None

    monkeypatch.setattr(main, "init_db", fake_init_db)

    stub_evaluator = StubEvaluatorStub()
    monkeypatch.setattr(main, "create_async_channel", lambda settings: StubChannel())
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
            raise main.HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Missing API key")
        if key != "valid-key":
            raise main.HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid API key")
        return security.AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key=key)

    app.dependency_overrides[main.require_api_key] = override_require_api_key

    app.state.redis = StubRedis.from_url("redis://test")
    app.state.cache = StubCache()
    app.state.job_cache = StubJobCache()
    app.state.rate_limit_key = StubRateLimiter()
    app.state.rate_limit_ip = StubRateLimiter()
    app.state.job_rate_limit_key = StubRateLimiter()
    app.state.quota_config = main.QuotaConfig(limit=main.settings.quota.limit, window_seconds=main.settings.quota.window_seconds)
    app.state.grpc_channel = StubChannel()
    app.state.grpc_stub = stub_evaluator

    recorded_jobs: dict[str, SimpleNamespace] = {}

    async def fake_count_queued_jobs(session):
        return fake_count_queued_jobs.value

    fake_count_queued_jobs.value = 0

    async def fake_create_job(session, submission, settings):
        job_id = f"job-{len(recorded_jobs) + 1}"
        job = SimpleNamespace(
            id=job_id,
            status="queued",
            created_at=dt.datetime.utcnow(),
            started_at=None,
            completed_at=None,
            priority=submission.priority,
            tags=list(submission.tags),
            context=submission.context,
            input_expression=submission.input_expression,
            result_payload=None,
            error=None,
        )
        recorded_jobs[job_id] = job
        return job

    def fake_serialize_job(job, settings):
        return {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "priority": job.priority,
            "tags": list(job.tags),
            "links": {
                "self": f"/jobs/{job.id}",
                "poll": f"/jobs/{job.id}",
                "result": f"/jobs/{job.id}",
                "ws": f"/ws/jobs/{job.id}",
            },
            "result_payload": job.result_payload,
            "error": job.error,
        }

    async def fake_fetch_job(session, job_id):
        return recorded_jobs.get(job_id)

    monkeypatch.setattr(main.jobs, "count_queued_jobs", fake_count_queued_jobs)
    monkeypatch.setattr(main.jobs, "create_job", fake_create_job)
    monkeypatch.setattr(main.jobs, "serialize_job", fake_serialize_job)
    monkeypatch.setattr(main.jobs, "fetch_job", fake_fetch_job)

    enqueue_calls: list[dict] = []

    def fake_enqueue_job(job_id: str, trace_context=None):
        enqueue_calls.append({"id": job_id, "trace": trace_context or {}})

    monkeypatch.setattr(main, "enqueue_job", fake_enqueue_job)

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
        "job_cache": app.state.job_cache,
        "job_rate_limiter": app.state.job_rate_limit_key,
        "enqueue_job_calls": enqueue_calls,
        "jobs_storage": recorded_jobs,
        "count_queued_jobs": fake_count_queued_jobs,
        "create_job_stub": fake_create_job,
    }

    recorded_audits.clear()
    app.dependency_overrides.clear()
    sys.modules.pop("app.instrumentation", None)
    sys.modules.pop("opentelemetry", None)
    sys.modules.pop("opentelemetry.trace", None)
    sys.modules.pop("opentelemetry.propagate", None)
    sys.modules.pop("opentelemetry.context", None)


def _make_request(host="127.0.0.1", *, method="POST", path="/calculate"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [],
        "client": (host, 1234),
    }
    from starlette.requests import Request

    return Request(scope, receive=lambda: None)


def test_calculate_success_invokes_evaluator(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    ExpressionRequest = ctx["schemas"].ExpressionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    payload = ExpressionRequest(expression="1+2")
    request = _make_request()
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    response = asyncio.run(main.calculate_sync(payload, request, api_key=api_key, session=session))

    assert response.value == pytest.approx(3.0)
    assert response.from_cache is False
    assert len(ctx["evaluator"].calls) == 1
    asyncio.run(asyncio.sleep(0))
    assert ctx["recorded_audits"], "audit log should capture success"


def test_calculate_uses_cache_on_repeated_calls(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    ExpressionRequest = ctx["schemas"].ExpressionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    payload = ExpressionRequest(expression="2*3")
    request = _make_request()
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    first = asyncio.run(main.calculate_sync(payload, request, api_key=api_key, session=session))
    assert first.from_cache is False
    second = asyncio.run(main.calculate_sync(payload, request, api_key=api_key, session=session))
    assert second.from_cache is True
    assert len(ctx["evaluator"].calls) == 1


def test_rate_limit_rejection_returns_http_429(gateway_test_context):
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
        asyncio.run(main.calculate_sync(payload, request, api_key=api_key, session=session))

    assert exc.value.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_submit_job_enqueues_and_caches_metadata(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    JobSubmissionRequest = ctx["schemas"].JobSubmissionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    payload = JobSubmissionRequest(input_expression="1+2")
    request = _make_request(path="/jobs")
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    response = asyncio.run(main.submit_job(payload, request, api_key=api_key, session=session))

    assert response.status == "queued"
    assert ctx["enqueue_job_calls"], "job dispatch should be recorded"
    job_id = ctx["enqueue_job_calls"][0]["id"]
    assert job_id == response.id
    cached = asyncio.run(ctx["job_cache"].get(job_id))
    assert cached["id"] == job_id


def test_submit_job_rate_limited_returns_http_429(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    JobSubmissionRequest = ctx["schemas"].JobSubmissionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    ctx["job_rate_limiter"].allowed = False
    payload = JobSubmissionRequest(input_expression="sin(0)")
    request = _make_request(path="/jobs")
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.submit_job(payload, request, api_key=api_key, session=session))

    assert exc.value.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_submit_job_queue_full_returns_503(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    JobSubmissionRequest = ctx["schemas"].JobSubmissionRequest
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey

    ctx["count_queued_jobs"].value = main.settings.job.max_queue_size
    payload = JobSubmissionRequest(input_expression="3*3")
    request = _make_request(path="/jobs")
    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.submit_job(payload, request, api_key=api_key, session=session))

    assert exc.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    ctx["count_queued_jobs"].value = 0


def test_get_job_fetches_from_persistence_when_cache_miss(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]
    AuthenticatedAPIKey = ctx["security"].AuthenticatedAPIKey
    JobSubmissionRequest = ctx["schemas"].JobSubmissionRequest

    submission = JobSubmissionRequest(input_expression="4+4")
    job = asyncio.run(ctx["create_job_stub"](StubSession(), submission, settings=main.settings))
    ctx["job_cache"].storage.pop(job.id, None)

    api_key = AuthenticatedAPIKey(record=SimpleNamespace(id=123), raw_key="valid-key")
    session = StubSession()

    response = asyncio.run(main.get_job(job.id, api_key=api_key, session=session))

    assert response.id == job.id
    assert asyncio.run(ctx["job_cache"].get(job.id)) is not None


def test_quota_exceeded_returns_http_429(gateway_test_context):
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
        asyncio.run(main.calculate_sync(payload, request, api_key=api_key, session=session))

    assert exc.value.status_code == HTTPStatus.TOO_MANY_REQUESTS


def test_require_api_key_missing_header_raises_401(gateway_test_context):
    ctx = gateway_test_context
    main = ctx["main"]

    scope = {"type": "http", "method": "POST", "path": "/calculate", "headers": [], "client": ("127.0.0.1", 1234)}
    from starlette.requests import Request

    request = Request(scope, receive=lambda: None)

    with pytest.raises(main.HTTPException) as exc:
        asyncio.run(main.require_api_key(request, session=StubSession()))

    assert exc.value.status_code == HTTPStatus.UNAUTHORIZED
