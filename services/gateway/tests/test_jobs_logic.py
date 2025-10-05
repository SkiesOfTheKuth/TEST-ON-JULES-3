import json
from pathlib import Path

import pytest
import pytest_asyncio
from celery.result import EagerResult
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.gateway.app import jobs, task_queue
from services.gateway.app.config import GatewaySettings
from services.gateway.app.models import Base
from services.gateway.app.schemas import JobSubmissionRequest
from services.protos import evaluator_pb2


class _RecordingRedis:
    """Test double that records cache writes."""

    last_instance: "_RecordingRedis | None" = None

    def __init__(self) -> None:
        self.storage: dict[str, str] = {}
        self.events: list[tuple[str, str, str | None]] = []

    @classmethod
    def from_url(cls, url: str, decode_responses: bool = True) -> "_RecordingRedis":  # noqa: D401
        cls.last_instance = cls()
        return cls.last_instance

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.storage[key] = value
        self.events.append(("set", key, value))

    async def delete(self, key: str) -> None:
        self.storage.pop(key, None)
        self.events.append(("delete", key, None))

    async def llen(self, key: str) -> int:
        self.events.append(("llen", key, None))
        return 0

    async def publish(self, channel: str, message: str) -> int:
        self.events.append(("publish", channel, message))
        return 1

    async def close(self) -> None:  # pragma: no cover - provided for API parity
        return None


class _InMemoryJobCache:
    def __init__(self) -> None:
        self.records: dict[str, dict] = {}

    async def set(self, job_id: str, payload: dict) -> None:
        self.records[job_id] = payload


@pytest.fixture
def test_settings(tmp_path: Path) -> GatewaySettings:
    db_path = tmp_path / "gateway.db"
    return GatewaySettings(
        database={"url": f"sqlite+aiosqlite:///{db_path}", "pool_size": 1, "pool_timeout": 5},
        redis={
            "url": "redis://test",  # stubbed in tests
            "cache_namespace": "jobs",
            "cache_ttl_seconds": 30,
        },
        job={
            "queue_name": "test-jobs",
            "default_ttl_seconds": 30,
            "cache_namespace": "jobs",
            "priority_levels": 4,
            "retry_backoff_seconds": 0.1,
            "max_retries": 1,
        },
    )


@pytest_asyncio.fixture
async def engine(test_settings: GatewaySettings):
    engine = create_async_engine(test_settings.database.url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_job_persists_and_caches(engine, test_settings: GatewaySettings) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        submission = JobSubmissionRequest(
            input_expression="1 + 2",
            context={"x": 5},
            priority=5,
            tags=["Alpha", "alpha", "beta"],
        )
        metadata = jobs.JobCreationMetadata(
            tenant="test-tenant",
            queue_name=test_settings.job.queue_name,
            task_type="standard",
            policy_snapshot={},
            policy_violations=[],
            policy_enforced=False,
            estimated_runtime_ms=None,
            assigned_priority=None,
            requested_priority=submission.priority,
        )

        job = await jobs.create_job(session, submission, settings=test_settings, metadata=metadata)
        assert job.status == jobs.STATUS_QUEUED
        assert job.priority == 3
        assert job.tags == ["Alpha", "beta"]

        cached = _InMemoryJobCache()
        await jobs.write_job_cache(cached, job, test_settings)
        payload = cached.records[job.id]

        assert payload["status"] == jobs.STATUS_QUEUED
        assert payload["links"]["ws"].endswith(job.id)

        fetched = await jobs.fetch_job(session, job.id)
        assert fetched is not None
        assert fetched.input_expression == submission.input_expression


@pytest.mark.asyncio
async def test_celery_job_lifecycle_in_eager_mode(
    engine, test_settings: GatewaySettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        submission = JobSubmissionRequest(input_expression="40 + 2", context={}, priority=0, tags=[])
        metadata = jobs.JobCreationMetadata(
            tenant="test-tenant",
            queue_name=test_settings.job.queue_name,
            task_type="standard",
            policy_snapshot={},
            policy_violations=[],
            policy_enforced=False,
            estimated_runtime_ms=None,
            assigned_priority=None,
            requested_priority=submission.priority,
        )
        job = await jobs.create_job(
            session,
            submission,
            settings=test_settings,
            metadata=metadata,
        )

    monkeypatch.setattr(task_queue, "settings", test_settings)

    async def fake_get_engine(_settings):
        return engine

    monkeypatch.setattr(task_queue, "get_engine", fake_get_engine)
    monkeypatch.setattr(task_queue, "Redis", _RecordingRedis)

    stub_evaluator_calls: list[str] = []

    class _StubEvaluator:
        def Evaluate(self, request, timeout=None, metadata=None):
            stub_evaluator_calls.append(request.expression)
            return evaluator_pb2.EvaluateResponse(value=42.0, duration_ms=5.0)

    monkeypatch.setattr(task_queue, "_get_sync_stub", lambda: _StubEvaluator())
    task_queue._sync_stub = None
    task_queue._sync_channel = None

    previous_always_eager = task_queue.celery_app.conf.task_always_eager
    previous_eager_propagates = task_queue.celery_app.conf.task_eager_propagates
    task_queue.celery_app.conf.task_always_eager = True
    task_queue.celery_app.conf.task_eager_propagates = True

    try:
        result: EagerResult = task_queue.execute_job.apply(
            args=[job.id],
            kwargs={"queue_name": metadata.queue_name, "trace_context": {}},
        )
        payload = result.get(timeout=5)
    finally:
        task_queue.celery_app.conf.task_always_eager = previous_always_eager
        task_queue.celery_app.conf.task_eager_propagates = previous_eager_propagates

    assert payload["status"] == jobs.STATUS_SUCCEEDED
    assert stub_evaluator_calls == ["40 + 2"]

    redis = _RecordingRedis.last_instance
    assert redis is not None
    statuses = [json.loads(event[2])["status"] for event in redis.events if event[0] == "set"]
    assert statuses[0] == jobs.STATUS_RUNNING
    assert statuses[-1] == jobs.STATUS_SUCCEEDED

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        refreshed = await jobs.fetch_job(session, job.id)
        assert refreshed is not None
        result_payload = refreshed.result_payload

    assert result_payload["value"] == 42.0




def test_enqueue_job_applies_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    records: dict[str, object] = {}

    class _FakeSignature:
        def __init__(self, args, kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def apply_async(self, *, queue: str, headers: dict[str, str], **kwargs) -> None:
            records["queue"] = queue
            records["headers"] = headers
            records["args"] = self.args
            records["kwargs"] = self.kwargs
            records["apply_kwargs"] = kwargs

    class _FakeTask:
        def s(self, *args, **kwargs):
            records["s_args"] = args
            records["s_kwargs"] = kwargs
            return _FakeSignature(args, kwargs)

    monkeypatch.setattr(task_queue, "execute_job", _FakeTask(), raising=False)
    metric_calls: list[tuple[str, str]] = []
    monkeypatch.setattr(task_queue, "_record_job_enqueued", lambda queue: metric_calls.append(("enqueued", queue)))
    monkeypatch.setattr(task_queue, "_schedule_queue_depth_refresh", lambda queue: metric_calls.append(("refresh", queue)))

    trace_headers = {"traceparent": "00-abc"}
    task_queue.enqueue_job("job-123", trace_context=trace_headers)

    default_queue = task_queue.settings.job.queue_name
    assert records["s_args"] == ("job-123",)
    assert records["s_kwargs"] == {"queue_name": default_queue, "trace_context": trace_headers}
    assert records["queue"] == default_queue
    assert records["headers"] == trace_headers
    assert records["apply_kwargs"].get("routing_key") == default_queue
    assert metric_calls == [("enqueued", default_queue), ("refresh", default_queue)], "Metrics hooks should be invoked"
