import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import httpx
import pytest
import pytest_asyncio
import websockets
from redis.asyncio import Redis
from sqlalchemy import delete, select

from app.autoscale import AutoscaleObservation, evaluate_autoscale
from app.config import GatewaySettings, get_settings
from app.database import get_session
from app.models import APIKey, TenantPolicy

pytestmark = pytest.mark.integration

_DEFAULT_BASE_URL = "http://localhost:8080"


@asynccontextmanager
async def session_scope():
    generator = get_session()
    try:
        session = await anext(generator)
        yield session
    finally:
        await generator.aclose()


@pytest_asyncio.fixture(scope="session")
def settings() -> GatewaySettings:
    return get_settings()


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.getenv("GATEWAY_TEST_BASE_URL", _DEFAULT_BASE_URL).rstrip("/")


@pytest.fixture(scope="session")
def api_key() -> str:
    key = os.getenv("TEST_GATEWAY_API_KEY")
    if not key:
        pytest.skip("TEST_GATEWAY_API_KEY is not set; integration stack must seed a key")
    return key


@pytest_asyncio.fixture(scope="function")
async def redis_client(settings: GatewaySettings) -> Redis:
    client = Redis.from_url(settings.redis.url, decode_responses=True)
    try:
        yield client
    finally:
        await client.close()


@pytest_asyncio.fixture(scope="function")
async def http_client(base_url: str, api_key: str) -> httpx.AsyncClient:
    headers = {"X-Api-Key": api_key}
    async with httpx.AsyncClient(base_url=base_url, headers=headers, timeout=10.0) as client:
        yield client


@pytest_asyncio.fixture(scope="function")
async def tenant_name() -> str:
    async with session_scope() as session:
        result = await session.execute(select(APIKey.owner).limit(1))
        owner = result.scalar_one_or_none()
        if owner is None:
            pytest.skip("No API key owner seeded; seed_api_key must run before integration tests")
        return owner


async def apply_policy(
    settings: GatewaySettings,
    tenant: str,
    redis: Redis,
    *,
    allow_heavy: bool,
    allow_gpu: bool,
    allowed_queues: List[str] | None = None,
    max_priority: int | None = None,
) -> None:
    if allowed_queues is None:
        allowed_queues = [
            settings.job.queue_name,
            settings.job.heavy_queue_name,
            settings.job.gpu_queue_name,
        ]
    if max_priority is None:
        max_priority = settings.job.priority_levels - 1

    async with session_scope() as session:
        await session.execute(delete(TenantPolicy).where(TenantPolicy.tenant == tenant))
        policy = TenantPolicy(
            tenant=tenant,
            description="integration-test-policy",
            allowed_queues=allowed_queues,
            max_priority=max_priority,
            max_runtime_ms=settings.job.default_max_runtime_ms,
            banned_patterns=[],
            allow_heavy=allow_heavy,
            allow_gpu=allow_gpu,
            quota_limit=settings.quota.limit,
            quota_window_seconds=settings.quota.window_seconds,
        )
        session.add(policy)
        await session.commit()

    await redis.delete(_policy_cache_key(settings, tenant))


async def clear_policy(settings: GatewaySettings, tenant: str, redis: Redis) -> None:
    async with session_scope() as session:
        await session.execute(delete(TenantPolicy).where(TenantPolicy.tenant == tenant))
        await session.commit()
    await redis.delete(_policy_cache_key(settings, tenant))


def _policy_cache_key(settings: GatewaySettings, tenant: str) -> str:
    namespace = settings.job.policy_cache_namespace or "policy"
    return f"{namespace}:{tenant}"


async def submit_job(client: httpx.AsyncClient, payload: Dict[str, Any]) -> Dict[str, Any]:
    response = await client.post("/jobs", json=payload)
    assert response.status_code == 202, response.text
    return response.json()


async def wait_for_completion(
    client: httpx.AsyncClient,
    job_id: str,
    *,
    timeout: float = 40.0,
    poll_interval: float = 0.5,
) -> Dict[str, Any]:
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        response = await client.get(f"/jobs/{job_id}")
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") not in {"queued", "running"}:
            return payload
        await asyncio.sleep(poll_interval)
    pytest.fail(f"Job {job_id} did not complete within {timeout} seconds")


async def collect_websocket_messages(
    base_url: str,
    api_key: str,
    job_id: str,
    *,
    timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    if base_url.startswith("https://"):
        ws_base = "wss://" + base_url[len("https://") :]
    elif base_url.startswith("http://"):
        ws_base = "ws://" + base_url[len("http://") :]
    else:
        ws_base = base_url
    uri = f"{ws_base}/ws/jobs/{job_id}"
    messages: List[Dict[str, Any]] = []
    async with websockets.connect(
        uri,
        extra_headers={"X-Api-Key": api_key},
        open_timeout=5,
        ping_interval=None,
    ) as websocket:
        start = time.perf_counter()
        while time.perf_counter() - start < timeout:
            try:
                raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            except asyncio.TimeoutError:
                pytest.fail("Timed out waiting for WebSocket job updates")
            messages.append(json.loads(raw))
            if messages[-1].get("status") in {"succeeded", "failed"}:
                break
    return messages


async def fetch_metrics(client: httpx.AsyncClient) -> str:
    response = await client.get("/metrics")
    response.raise_for_status()
    return response.text


@pytest.mark.asyncio
async def test_jobs_route_to_expected_queues(
    http_client: httpx.AsyncClient,
    redis_client: Redis,
    settings: GatewaySettings,
    tenant_name: str,
):
    await apply_policy(settings, tenant_name, redis_client, allow_heavy=True, allow_gpu=True)
    try:
        standard_job = await submit_job(
            http_client,
            {"input_expression": "21 + 21"},
        )
        heavy_job = await submit_job(
            http_client,
            {
                "input_expression": "integrate(x**2, x)",
                "tags": ["heavy"],
            },
        )
        gpu_job = await submit_job(
            http_client,
            {
                "input_expression": "sin(x) + cos(x)",
                "tags": ["gpu"],
            },
        )

        standard_result = await wait_for_completion(http_client, standard_job["id"])
        heavy_result = await wait_for_completion(http_client, heavy_job["id"])
        gpu_result = await wait_for_completion(http_client, gpu_job["id"])

        assert standard_result["status"] == "succeeded"
        assert standard_result["queue_name"] == settings.job.queue_name
        assert heavy_result["status"] == "succeeded"
        assert heavy_result["queue_name"] == settings.job.heavy_queue_name
        assert heavy_result["task_type"] == "heavy"
        assert gpu_result["status"] == "succeeded"
        assert gpu_result["queue_name"] == settings.job.gpu_queue_name
        assert gpu_result["task_type"] == "gpu"

        metrics = await fetch_metrics(http_client)
        for queue in [
            settings.job.queue_name,
            settings.job.heavy_queue_name,
            settings.job.gpu_queue_name,
        ]:
            assert (
                f"calculator_gateway_jobs_enqueued_total{{queue=\"{queue}\"" in metrics
            ), f"Missing enqueue metric for queue {queue}"
            assert (
                f"calculator_gateway_job_queue_depth{{queue=\"{queue}\"" in metrics
            ), f"Missing queue depth metric for queue {queue}"
    finally:
        await clear_policy(settings, tenant_name, redis_client)


@pytest.mark.asyncio
async def test_policy_enforcement_blocks_gpu_when_disallowed(
    http_client: httpx.AsyncClient,
    redis_client: Redis,
    settings: GatewaySettings,
    tenant_name: str,
):
    await apply_policy(
        settings,
        tenant_name,
        redis_client,
        allow_heavy=False,
        allow_gpu=False,
        allowed_queues=[settings.job.queue_name],
        max_priority=0,
    )
    try:
        response = await http_client.post(
            "/jobs",
            json={
                "input_expression": "sqrt(4)",
                "requires_gpu": True,
            },
        )
        assert response.status_code == 403
        payload = response.json()
        assert payload["detail"]["error"] == "policy_violation"
        assert "gpu_required" in payload["detail"]["violations"][0]
    finally:
        await clear_policy(settings, tenant_name, redis_client)


@pytest.mark.asyncio
async def test_websocket_emits_job_lifecycle_events(
    base_url: str,
    api_key: str,
    http_client: httpx.AsyncClient,
    redis_client: Redis,
    settings: GatewaySettings,
    tenant_name: str,
):
    await apply_policy(settings, tenant_name, redis_client, allow_heavy=True, allow_gpu=False)
    try:
        job = await submit_job(
            http_client,
            {
                "input_expression": "(18 + 24) / 2",
            },
        )
        ws_task = asyncio.create_task(
            collect_websocket_messages(base_url, api_key, job["id"])
        )
        result = await wait_for_completion(http_client, job["id"])
        messages = await ws_task
        assert result["status"] == "succeeded"
        statuses = [msg.get("status") for msg in messages if "status" in msg]
        assert statuses, "WebSocket stream returned no status updates"
        assert statuses[0] == "queued"
        assert statuses[-1] == result["status"]
    finally:
        await clear_policy(settings, tenant_name, redis_client)


@pytest.mark.asyncio
async def test_failed_job_records_metrics(
    http_client: httpx.AsyncClient,
    redis_client: Redis,
    settings: GatewaySettings,
    tenant_name: str,
):
    await apply_policy(settings, tenant_name, redis_client, allow_heavy=True, allow_gpu=True)
    try:
        job = await submit_job(
            http_client,
            {
                "input_expression": "x + 1",
                "context": {"1invalid": 2},
            },
        )
        result = await wait_for_completion(http_client, job["id"])
        assert result["status"] == "failed"
        assert result.get("error")

        metrics = await fetch_metrics(http_client)
        assert "calculator_gateway_jobs_failed_total" in metrics
        assert settings.job.queue_name in metrics
    finally:
        await clear_policy(settings, tenant_name, redis_client)


@pytest.mark.asyncio
async def test_autoscale_recommends_scale_up(settings: GatewaySettings) -> None:
    observation = AutoscaleObservation(
        queue_depth=settings.autoscale.scale_up_queue_threshold + 5,
        active_workers=settings.autoscale.min_workers,
        p95_wait_seconds=settings.autoscale.target_queue_wait_p95_seconds + 1,
        worker_cpu_percent=settings.autoscale.target_cpu_percent + 5,
        last_scale_timestamp=None,
    )
    decision = evaluate_autoscale(observation, settings.autoscale)
    assert decision.action == "scale_up"
    assert decision.desired_workers > observation.active_workers