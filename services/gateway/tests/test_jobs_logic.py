import json
from pathlib import Path

import asyncio
import pytest
from celery.result import EagerResult
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from services.gateway.app import jobs, task_queue
from services.gateway.app.config import DatabaseSettings, GatewaySettings, JobSettings, RedisSettings
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
        database=DatabaseSettings(url=f"sqlite+aiosqlite:///{db_path}", pool_size=1, pool_timeout=5),
        redis=RedisSettings(
            url="redis://test",
            cache_namespace="jobs",
            cache_ttl_seconds=30,
        ),
        job=JobSettings(
            queue_name="test-jobs",
            default_ttl_seconds=30,
            cache_namespace="jobs",
            priority_levels=4,
            retry_backoff_seconds=0.1,
            max_retries=1,
        ),
    )


@pytest.fixture
def engine(test_settings: GatewaySettings):
    db_settings = test_settings.database
    db_url = db_settings.url if hasattr(db_settings, "url") else db_settings["url"]
    engine = create_async_engine(db_url)

    async def _prepare() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_prepare())

    yield engine

    asyncio.run(engine.dispose())


def test_create_job_persists_and_caches(engine, test_settings: GatewaySettings) -> None:
    async def _run() -> None:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            submission = JobSubmissionRequest(
                input_expression="1 + 2",
                context={"x": 5},
                priority=5,
                tags=["Alpha", "alpha", "beta"],
            )

            job = await jobs.create_job(session, submission, settings=test_settings)
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

    asyncio.run(_run())


def test_celery_job_lifecycle_in_eager_mode(
    engine, test_settings: GatewaySettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _setup_job() -> str:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            job = await jobs.create_job(
                session,
                JobSubmissionRequest(input_expression="40 + 2", context={}, priority=0, tags=[]),
                settings=test_settings,
            )
        return job.id

    job_id = asyncio.run(_setup_job())

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
        result: EagerResult = task_queue.execute_job.apply(args=[job_id], kwargs={"trace_context": {}})
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

    async def _fetch_result() -> dict:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            refreshed = await jobs.fetch_job(session, job_id)
            assert refreshed is not None
            return refreshed.result_payload

    result_payload = asyncio.run(_fetch_result())

    assert result_payload["value"] == 42.0

