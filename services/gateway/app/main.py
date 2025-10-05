"""FastAPI application for the calculator gateway."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Dict

from services.common.grpc import grpc
from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind, Status, StatusCode
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from services.protos import evaluator_pb2, evaluator_pb2_grpc

from . import jobs
from .cache import JobCache, ResultCache
from .config import get_settings
from .database import get_session, init_db
from .evaluator_client import build_grpc_metadata, create_async_channel
from .instrumentation import (
    configure_logging,
    configure_tracing,
    get_policy_context,
    instrument_app,
    record_policy_decision,
    record_rate_limit_rejection,
    set_policy_context,
    set_queue_context,
    set_tenant_context,
)
from .models import RequestAudit
from .quota import QuotaConfig, QuotaExceededError, consume_quota
from .policy import evaluate_job_policy
from .rate_limit import RateLimiter
from .schemas import (
    CalculationResponse,
    ExpressionRequest,
    JobResultResponse,
    JobSubmissionRequest,
)
from .security import AuthenticatedAPIKey, get_api_key
from .task_queue import enqueue_job

logger = logging.getLogger(__name__)

settings = get_settings()
configure_logging(settings)
configure_tracing(settings)
app = FastAPI(title="Calculator Gateway", version="1.0.0")
instrument_app(app, settings)

tracer = trace.get_tracer(__name__)


@app.on_event("startup")
async def startup_event() -> None:
    app.state.settings = settings
    app.state.redis = Redis.from_url(settings.redis.url, decode_responses=True)
    app.state.cache = ResultCache(
        app.state.redis,
        settings.redis.cache_ttl_seconds,
        namespace=settings.redis.cache_namespace,
    )
    app.state.job_cache = JobCache(
        app.state.redis,
        settings.job.default_ttl_seconds,
        namespace=settings.job.cache_namespace,
    )
    rate_counter_ttl = settings.redis.rate_counter_ttl_seconds
    app.state.rate_limit_key = RateLimiter(
        app.state.redis,
        settings.redis.rate_limit_requests,
        settings.redis.rate_limit_window_seconds,
        settings.redis.rate_namespace,
        ttl_seconds=rate_counter_ttl,
    )
    app.state.rate_limit_ip = RateLimiter(
        app.state.redis,
        settings.redis.rate_limit_requests * 2,
        settings.redis.rate_limit_window_seconds,
        settings.redis.limiter_namespace,
        ttl_seconds=rate_counter_ttl,
    )
    app.state.job_rate_limit_key = RateLimiter(
        app.state.redis,
        settings.job.rate_limit_requests,
        settings.job.rate_limit_window_seconds,
        settings.job.rate_namespace,
        ttl_seconds=rate_counter_ttl,
    )
    app.state.quota_config = QuotaConfig(
        limit=settings.quota.limit,
        window_seconds=settings.quota.window_seconds,
    )
    await init_db(settings)
    app.state.grpc_channel = create_async_channel(settings.evaluator)
    app.state.grpc_stub = evaluator_pb2_grpc.EvaluatorStub(app.state.grpc_channel)
    logger.info("Gateway started on %s:%s", settings.host, settings.port)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    redis: Redis = app.state.redis
    await redis.close()
    await app.state.grpc_channel.close()


async def require_api_key(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> AuthenticatedAPIKey:
    raw_key = request.headers.get("X-Api-Key")
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    record = await get_api_key(session, raw_key)
    if not record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return record


@app.post("/calculate-sync", response_model=CalculationResponse)
async def calculate_sync(
    payload: ExpressionRequest,
    request: Request,
    api_key: AuthenticatedAPIKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> CalculationResponse:
    tenant = api_key.record.owner
    set_tenant_context(tenant)
    set_queue_context("sync")
    set_policy_context("pending")
    root_span = trace.get_current_span()
    if root_span and root_span.is_recording():
        root_span.set_attribute("calculator.tenant", tenant)
        root_span.set_attribute("calculator.queue", "sync")
        root_span.set_attribute("calculator.policy_outcome", "pending")

    def _record_policy(decision: str, rule: str) -> None:
        record_policy_decision(tenant=tenant, rule=rule, decision=decision)
        set_policy_context(decision)
        current = trace.get_current_span()
        if current and current.is_recording():
            current.set_attribute("calculator.policy_outcome", decision)
        if root_span and root_span.is_recording():
            root_span.set_attribute("calculator.policy_outcome", decision)

    client_ip = request.client.host if request.client else "unknown"
    api_key_id = api_key.record.id
    rate_limiter_key: RateLimiter = app.state.rate_limit_key
    rate_limiter_ip: RateLimiter = app.state.rate_limit_ip
    expression_hash = payload.hash(api_key.raw_key)

    if not await rate_limiter_key.allow(str(api_key_id)):
        record_rate_limit_rejection("api_key")
        _record_policy("deny", "api_rate_limit")
        await _persist_audit(
            api_key_id,
            expression_hash,
            payload.expression,
            client_ip,
            "rate_limit_key",
            0.0,
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="API key rate limit exceeded")
    if not await rate_limiter_ip.allow(client_ip):
        record_rate_limit_rejection("ip")
        _record_policy("deny", "ip_rate_limit")
        await _persist_audit(
            api_key_id,
            expression_hash,
            payload.expression,
            client_ip,
            "rate_limit_ip",
            0.0,
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="IP rate limit exceeded")

    try:
        await consume_quota(session, api_key_id, app.state.quota_config)
    except QuotaExceededError as exc:
        _record_policy("deny", "quota")
        await _persist_audit(
            api_key_id,
            expression_hash,
            payload.expression,
            client_ip,
            "quota_exceeded",
            0.0,
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    cache: ResultCache = app.state.cache
    cache_key = expression_hash
    should_use_cache = settings.cache_pure_results and payload.is_pure_arithmetic()
    cached_value = await cache.get(cache_key) if should_use_cache else None
    if cached_value is not None:
        _record_policy("allow", "cache_hit")
        await _persist_audit(
            api_key_id,
            cache_key,
            payload.expression,
            client_ip,
            "cache_hit",
            0.0,
        )
        return CalculationResponse(
            expression=payload.expression,
            value=cached_value,
            duration_ms=0.0,
            from_cache=True,
        )

    stub: evaluator_pb2_grpc.EvaluatorStub = app.state.grpc_stub
    request_message = evaluator_pb2.EvaluateRequest(
        expression=payload.expression,
        context={k: str(v) for k, v in payload.context.items()},
    )

    start_time = time.perf_counter()
    try:
        request_id = getattr(request.state, "request_id", None)
        metadata = build_grpc_metadata(request_id=request_id)
        with tracer.start_as_current_span(
            "gateway.grpc.evaluate",
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attribute("rpc.system", "grpc")
            span.set_attribute("rpc.service", "calculator.Evaluator")
            span.set_attribute("rpc.method", "Evaluate")
            span.set_attribute("net.peer.name", settings.evaluator.host)
            span.set_attribute("net.peer.port", settings.evaluator.port)
            span.set_attribute("calculator.tenant", tenant)
            span.set_attribute("calculator.queue", "sync")
            span.set_attribute("calculator.policy_outcome", get_policy_context())
            try:
                response = await stub.Evaluate(
                    request_message,
                    timeout=settings.evaluator.deadline_ms / 1000,
                    metadata=metadata,
                )
            except grpc.AioRpcError as exc:
                span.record_exception(exc)
                span.set_attribute("rpc.grpc.status_code", exc.code().name)
                span.set_status(Status(StatusCode.ERROR, exc.details() or exc.code().name))
                raise
            else:
                span.set_attribute("rpc.grpc.status_code", grpc.StatusCode.OK.name)
                span.set_status(Status(StatusCode.OK))
    except grpc.AioRpcError as exc:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        status_code = exc.code()
        detail = exc.details() or "Evaluator unavailable"
        if status_code == grpc.StatusCode.INVALID_ARGUMENT:
            _record_policy("deny", "invalid_expression")
            await _persist_audit(
                api_key_id,
                expression_hash,
                payload.expression,
                client_ip,
                "invalid_expression",
                elapsed_ms,
            )
            return CalculationResponse(
                expression=payload.expression,
                error=detail,
                duration_ms=elapsed_ms,
                from_cache=False,
            )
        if status_code == grpc.StatusCode.RESOURCE_EXHAUSTED:
            _record_policy("deny", "evaluator_rate_limit")
            await _persist_audit(
                api_key_id,
                expression_hash,
                payload.expression,
                client_ip,
                "evaluator_rate_limited",
                elapsed_ms,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Evaluator busy",
            ) from exc
        _record_policy("error", "evaluator_error")
        logger.exception("Evaluator call failed")
        await _persist_audit(
            api_key_id,
            expression_hash,
            payload.expression,
            client_ip,
            "evaluator_error",
            elapsed_ms,
        )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Evaluator unavailable") from exc

    duration_ms = response.duration_ms or (time.perf_counter() - start_time) * 1000
    result_type = response.WhichOneof("result")

    if result_type == "error":
        _record_policy("error", "calculation_error")
        await _persist_audit(
            api_key_id,
            expression_hash,
            payload.expression,
            client_ip,
            "evaluation_error",
            duration_ms,
        )
        return CalculationResponse(
            expression=payload.expression,
            error=response.error,
            duration_ms=duration_ms,
            from_cache=False,
        )

    if should_use_cache:
        await cache.set(cache_key, response.value)

    asyncio.create_task(
        _persist_audit(
            api_key_id,
            cache_key,
            payload.expression,
            client_ip,
            "success",
            duration_ms,
        )
    )

    _record_policy("allow", "sync_execution")
    return CalculationResponse(
        expression=payload.expression,
        value=response.value,
        duration_ms=duration_ms,
        from_cache=False,
    )


@app.post("/calculate", response_model=CalculationResponse)
async def calculate(
    payload: ExpressionRequest,
    request: Request,
    api_key: AuthenticatedAPIKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> CalculationResponse:
    return await calculate_sync(payload, request, api_key=api_key, session=session)


@app.post("/jobs", response_model=JobResultResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    payload: JobSubmissionRequest,
    request: Request,
    api_key: AuthenticatedAPIKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> JobResultResponse:
    tenant = api_key.record.owner
    set_tenant_context(tenant)
    set_queue_context(settings.job.queue_name)
    set_policy_context("pending")
    root_span = trace.get_current_span()
    if root_span and root_span.is_recording():
        root_span.set_attribute("calculator.tenant", tenant)
        root_span.set_attribute("calculator.queue", settings.job.queue_name)
        root_span.set_attribute("calculator.policy_outcome", "pending")

    def _record_policy(decision: str, rule: str) -> None:
        record_policy_decision(tenant=tenant, rule=rule, decision=decision)
        set_policy_context(decision)
        current = trace.get_current_span()
        if current and current.is_recording():
            current.set_attribute("calculator.policy_outcome", decision)
        if root_span and root_span.is_recording():
            root_span.set_attribute("calculator.policy_outcome", decision)

    api_key_id = api_key.record.id
    job_rate_limiter: RateLimiter = app.state.job_rate_limit_key
    if not await job_rate_limiter.allow(str(api_key_id)):
        record_rate_limit_rejection("job_api_key")
        _record_policy("deny", "job_rate_limit")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="API key job rate limit exceeded",
        )

    if settings.job.max_queue_size > 0:
        queued_jobs = await jobs.count_queued_jobs(session)
        if queued_jobs >= settings.job.max_queue_size:
            _record_policy("deny", "queue_capacity")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Job queue is full",
            )

    policy_decision = await evaluate_job_policy(
        session,
        app.state.redis,
        tenant=tenant,
        submission=payload,
        settings=settings,
        base_quota=app.state.quota_config,
    )

    set_queue_context(policy_decision.queue_name)
    if root_span and root_span.is_recording():
        root_span.set_attribute("calculator.queue", policy_decision.queue_name)
        root_span.set_attribute("job.queue_name", policy_decision.queue_name)
        root_span.set_attribute("job.task_type", policy_decision.task_type)
        root_span.set_attribute("job.requested_priority", policy_decision.requested_priority)
        root_span.set_attribute("job.assigned_priority", policy_decision.normalized_priority)
        root_span.set_attribute("job.policy_enforced", policy_decision.policy_enforced)
        root_span.set_attribute("job.policy_violation_count", len(policy_decision.violations))

    if not policy_decision.allowed:
        _record_policy("deny", "policy_violation")
        for violation in policy_decision.violations:
            record_policy_decision(tenant=tenant, rule=violation, decision="violation")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "policy_violation",
                "reason": policy_decision.denial_reason,
                "violations": policy_decision.violations,
            },
        )

    _record_policy("allow", "job_submission")
    if policy_decision.policy_enforced:
        record_policy_decision(tenant=tenant, rule="policy_enforced", decision="violation")
    for violation in policy_decision.violations:
        record_policy_decision(tenant=tenant, rule=violation, decision="violation")

    try:
        await consume_quota(session, api_key_id, policy_decision.quota_config)
    except QuotaExceededError as exc:
        _record_policy("deny", "quota")
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc

    metadata = jobs.JobCreationMetadata(
        tenant=tenant,
        queue_name=policy_decision.queue_name,
        task_type=policy_decision.task_type,
        policy_snapshot=policy_decision.snapshot,
        policy_violations=policy_decision.violations,
        policy_enforced=policy_decision.policy_enforced,
        estimated_runtime_ms=policy_decision.estimated_runtime_ms,
        assigned_priority=policy_decision.normalized_priority,
        requested_priority=policy_decision.requested_priority,
    )

    job = await jobs.create_job(session, payload, settings=settings, metadata=metadata)
    job_cache: JobCache = app.state.job_cache
    job_payload = jobs.serialize_job(job, settings)
    await job_cache.set(job.id, job_payload)
    await jobs.publish_job_update(app.state.redis, job.id, job_payload, settings=settings)

    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("job.queue_name", job.queue_name)
        span.set_attribute("job.task_type", job.task_type)
        span.set_attribute("job.priority", job.priority)
        span.set_attribute("job.policy_enforced", policy_decision.policy_enforced)
        span.set_attribute("calculator.policy_outcome", get_policy_context())

    trace_headers: dict[str, str] = {}
    inject(trace_headers)
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        trace_headers.setdefault("x-request-id", request_id)
    trace_headers["calculator-tenant"] = tenant
    trace_headers["calculator-queue"] = job.queue_name
    trace_headers["calculator-policy"] = get_policy_context()
    trace_headers["calculator-task-type"] = job.task_type
    trace_headers["calculator-priority"] = str(job.priority)

    enqueue_job(job.id, queue_name=policy_decision.queue_name, trace_context=trace_headers)

    return JobResultResponse(**job_payload)


@app.get("/jobs/{job_id}", response_model=JobResultResponse)
async def get_job(
    job_id: str,
    api_key: AuthenticatedAPIKey = Depends(require_api_key),
    session: AsyncSession = Depends(get_session),
) -> JobResultResponse:
    job_cache: JobCache = app.state.job_cache
    cached = await job_cache.get(job_id)
    if cached is not None:
        return JobResultResponse(**cached)

    job = await jobs.fetch_job(session, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    payload = jobs.serialize_job(job, settings)
    await job_cache.set(job.id, payload)
    return JobResultResponse(**payload)


@app.websocket("/ws/jobs/{job_id}")
async def job_updates(websocket: WebSocket, job_id: str) -> None:
    authenticated = await _authenticate_websocket(websocket)
    if authenticated is None:
        return

    await websocket.accept()

    payload = await _load_job_payload(job_id)
    if payload is None:
        await websocket.send_json({"error": "job_not_found", "id": job_id})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.send_json(payload)

    redis = Redis.from_url(settings.redis.url, decode_responses=True)
    pubsub = redis.pubsub()
    channel = jobs.build_job_channel(settings, job_id)

    try:
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            data = message.get("data")
            if isinstance(data, (bytes, bytearray)):
                data = data.decode("utf-8")
            try:
                update = json.loads(data)
            except (TypeError, json.JSONDecodeError):
                continue
            await websocket.send_json(update)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await pubsub.unsubscribe(channel)
        finally:
            await pubsub.close()
            await redis.close()


@app.get("/health/live")
async def live() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/health/ready")
async def ready() -> JSONResponse:
    return JSONResponse({"status": "ready"})


async def _authenticate_websocket(websocket: WebSocket) -> AuthenticatedAPIKey | None:
    raw_key = websocket.headers.get("x-api-key") or websocket.headers.get("X-Api-Key")
    if not raw_key:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Missing API key")
        return None

    override = getattr(app, "dependency_overrides", {}).get(require_api_key)
    if override is not None:
        fake_request = SimpleNamespace(headers={"X-Api-Key": raw_key})
        result = override(fake_request)
        if inspect.isawaitable(result):
            result = await result
        return result

    session_gen = get_session()
    try:
        session = await anext(session_gen)
    except StopAsyncIteration:  # pragma: no cover - defensive
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return None

    try:
        record = await get_api_key(session, raw_key)
    finally:
        await session_gen.aclose()

    if record is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid API key")
        return None

    return record


async def _load_job_payload(job_id: str) -> Dict[str, Any] | None:
    job_cache: JobCache = app.state.job_cache
    cached = await job_cache.get(job_id)
    if cached is not None:
        return cached

    session_gen = get_session()
    try:
        session = await anext(session_gen)
    except StopAsyncIteration:  # pragma: no cover - defensive
        return None

    try:
        job = await jobs.fetch_job(session, job_id)
        if job is None:
            return None
        payload = jobs.serialize_job(job, settings)
        await job_cache.set(job.id, payload)
        return payload
    finally:
        await session_gen.aclose()


async def _persist_audit(
    api_key_id: int,
    expression_hash: str,
    expression: str,
    client_ip: str,
    outcome: str,
    latency_ms: float,
) -> None:
    async for session in get_session():
        audit = RequestAudit(
            api_key_id=api_key_id,
            expression_hash=expression_hash,
            expression=expression,
            client_ip=client_ip,
            outcome=outcome,
            latency_ms=latency_ms,
        )
        session.add(audit)
        await session.commit()
        break
