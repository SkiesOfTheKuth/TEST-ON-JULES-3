import asyncio
from pathlib import Path
from typing import Optional

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.gateway.app import jobs, task_queue
from services.common.grpc import grpc
from services.gateway.app.config import GatewaySettings
from services.gateway.app.jobs import JobCreationMetadata
from services.gateway.app.models import Base
from services.gateway.app.schemas import JobSubmissionRequest
from services.protos import evaluator_pb2


class _StubRedis:
    """Minimal Redis double that allows injecting failure modes."""


    def __init__(self, *, fail_llen: bool = False) -> None:
        self.fail_llen = fail_llen
        self.events: list[tuple[str, str]] = []

    @classmethod
    def from_url(cls, url: str, decode_responses: bool = True, **kwargs):  # type: ignore[override]
        return cls()

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        self.events.append(("set", key))

    async def delete(self, key: str) -> None:
        self.events.append(("delete", key))

    async def llen(self, key: str) -> int:
        self.events.append(("llen", key))
        if self.fail_llen:
            raise ConnectionError("redis offline")
        return 0

    async def publish(self, channel: str, message: str) -> int:
        self.events.append(("publish", channel))
        return 1

    async def close(self) -> None:  # pragma: no cover - compatibility shim
        return None


@pytest.fixture
def test_settings(tmp_path: Path) -> GatewaySettings:
    db_path = tmp_path / "gateway.db"
    return GatewaySettings(
        database={"url": f"sqlite+aiosqlite:///{db_path}", "pool_size": 1, "pool_timeout": 5},
        redis={
            "url": "redis://test",
            "cache_namespace": "jobs",
            "cache_ttl_seconds": 30,
        },
        job={
            "queue_name": "test-jobs",
            "heavy_queue_name": "test-jobs-heavy",
            "gpu_queue_name": "test-jobs-gpu",
            "default_ttl_seconds": 30,
            "cache_namespace": "jobs",
            "priority_levels": 4,
            "retry_backoff_seconds": 0.05,
            "max_retries": 2,
        },
    )


@pytest_asyncio.fixture
async def engine(test_settings: GatewaySettings):
    pytest.importorskip('aiosqlite')
    engine = create_async_engine(test_settings.database.url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


def _build_metadata(queue_name: str, *, tenant: str = "acme") -> JobCreationMetadata:
    return JobCreationMetadata(
        tenant=tenant,
        queue_name=queue_name,
        task_type="standard",
        policy_snapshot={"lane": "standard"},
        policy_violations=[],
        policy_enforced=False,
        estimated_runtime_ms=50,
        assigned_priority=1,
        requested_priority=1,
    )


@pytest.mark.asyncio
async def test_execute_job_handles_worker_slowdown(monkeypatch: pytest.MonkeyPatch, test_settings: GatewaySettings, engine) -> None:
    """Slow evaluator responses should still finalize successfully."""

    redis = _StubRedis()
    monkeypatch.setattr(task_queue, 'Redis', _StubRedis)
    monkeypatch.setattr(task_queue.Redis, 'from_url', classmethod(lambda cls, *args, **kwargs: redis))
    monkeypatch.setattr(task_queue, "settings", test_settings)
    monkeypatch.setattr(task_queue, "_PROCESS", None, raising=False)

    async def fake_get_engine(_settings):
        return engine

    monkeypatch.setattr(task_queue, "get_engine", fake_get_engine)

    async def slow_invoke(job, trace_headers):
        await asyncio.sleep(0.01)
        return evaluator_pb2.EvaluateResponse(value=3.14, duration_ms=5)

    monkeypatch.setattr(task_queue, "_invoke_evaluator", slow_invoke)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        job = await jobs.create_job(
            session,
            JobSubmissionRequest(input_expression="1+2", context={}, priority=1, tags=[]),
            settings=test_settings,
            metadata=_build_metadata(test_settings.job.queue_name),
        )

    payload = await task_queue._execute_job(
        job.id,
        queue_name=test_settings.job.queue_name,
        trace_headers={},
        attempt=0,
        max_retries=1,
    )

    assert payload["status"] == jobs.STATUS_SUCCEEDED
    await asyncio.sleep(0)  # ensure redis.close awaited
    redis_channels = {event for action, event in redis.events if action == "publish"}
    assert redis_channels, "WebSocket notifications should be emitted for the job"


@pytest.mark.asyncio
async def test_execute_job_recovers_from_redis_outage(monkeypatch: pytest.MonkeyPatch, test_settings: GatewaySettings, engine) -> None:
    """Queue depth probes must tolerate transient Redis connectivity failures."""

    redis = _StubRedis(fail_llen=True)
    monkeypatch.setattr(task_queue, 'Redis', _StubRedis)
    monkeypatch.setattr(task_queue.Redis, 'from_url', classmethod(lambda cls, *args, **kwargs: redis))
    monkeypatch.setattr(task_queue, "settings", test_settings)
    monkeypatch.setattr(task_queue, "_PROCESS", None, raising=False)

    async def fake_get_engine(_settings):
        return engine

    monkeypatch.setattr(task_queue, "get_engine", fake_get_engine)

    class _AlwaysSuccess:
        async def __call__(self, job, trace_headers):
            return evaluator_pb2.EvaluateResponse(value=1.0, duration_ms=2)

    monkeypatch.setattr(task_queue, "_invoke_evaluator", _AlwaysSuccess())

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        job = await jobs.create_job(
            session,
            JobSubmissionRequest(input_expression="2+2", context={}, priority=1, tags=[]),
            settings=test_settings,
            metadata=_build_metadata(test_settings.job.queue_name),
        )

    payload = await task_queue._execute_job(
        job.id,
        queue_name=test_settings.job.queue_name,
        trace_headers={},
        attempt=0,
        max_retries=1,
    )

    assert payload["status"] == jobs.STATUS_SUCCEEDED
    # llen failures should not abort execution; events still recorded for publish
    assert any(action == "publish" for action, _ in redis.events)


@pytest.mark.asyncio
async def test_transient_evaluator_failure_requests_retry(monkeypatch: pytest.MonkeyPatch, test_settings: GatewaySettings, engine) -> None:
    """Resource exhaustion from evaluator should raise TransientJobError for Celery retry."""

    redis = _StubRedis()
    monkeypatch.setattr(task_queue, 'Redis', _StubRedis)
    monkeypatch.setattr(task_queue.Redis, 'from_url', classmethod(lambda cls, *args, **kwargs: redis))
    monkeypatch.setattr(task_queue, "settings", test_settings)
    monkeypatch.setattr(task_queue, "_PROCESS", None, raising=False)

    async def fake_get_engine(_settings):
        return engine

    monkeypatch.setattr(task_queue, "get_engine", fake_get_engine)

    class _ResourceExhausted(grpc.RpcError):
        def __init__(self):
            self._code = grpc.StatusCode.RESOURCE_EXHAUSTED

        def code(self):
            return self._code

        def details(self):
            return "resource exhausted"

    async def failing_invoke(job, trace_headers):  # noqa: ANN001
        raise _ResourceExhausted()

    monkeypatch.setattr(task_queue, "_invoke_evaluator", failing_invoke)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        job = await jobs.create_job(
            session,
            JobSubmissionRequest(input_expression="3+3", context={}, priority=1, tags=[]),
            settings=test_settings,
            metadata=_build_metadata(test_settings.job.queue_name),
        )

    with pytest.raises(task_queue.TransientJobError):
        await task_queue._execute_job(
            job.id,
            queue_name=test_settings.job.queue_name,
            trace_headers={},
            attempt=0,
            max_retries=2,
        )


@pytest.mark.asyncio
async def test_worker_crash_marks_job_failed(monkeypatch: pytest.MonkeyPatch, test_settings: GatewaySettings, engine) -> None:
    """Unexpected worker exceptions should mark the job as failed with error payload."""

    redis = _StubRedis()
    monkeypatch.setattr(task_queue, 'Redis', _StubRedis)
    monkeypatch.setattr(task_queue.Redis, 'from_url', classmethod(lambda cls, *args, **kwargs: redis))
    monkeypatch.setattr(task_queue, "settings", test_settings)
    monkeypatch.setattr(task_queue, "_PROCESS", None, raising=False)

    async def fake_get_engine(_settings):
        return engine

    monkeypatch.setattr(task_queue, "get_engine", fake_get_engine)

    async def crashing_invoke(job, trace_headers):
        raise RuntimeError("worker crashed")

    monkeypatch.setattr(task_queue, "_invoke_evaluator", crashing_invoke)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        job = await jobs.create_job(
            session,
            JobSubmissionRequest(input_expression="4+4", context={}, priority=1, tags=[]),
            settings=test_settings,
            metadata=_build_metadata(test_settings.job.queue_name),
        )

    with pytest.raises(task_queue.JobExecutionError):
        await task_queue._execute_job(
            job.id,
            queue_name=test_settings.job.queue_name,
            trace_headers={},
            attempt=0,
            max_retries=1,
        )

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        refreshed = await jobs.fetch_job(session, job.id)
        assert refreshed is not None
        assert refreshed.status == jobs.STATUS_FAILED
        assert refreshed.error == "worker crashed"
