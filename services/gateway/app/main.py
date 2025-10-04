"""FastAPI application for the calculator gateway."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

import grpc
from opentelemetry import trace
from opentelemetry.propagate import inject
from opentelemetry.trace import SpanKind, Status, StatusCode
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from services.protos import evaluator_pb2, evaluator_pb2_grpc

from .cache import ResultCache
from .config import EvaluatorSettings, get_settings
from .database import get_session, init_db
from .instrumentation import (
    configure_logging,
    configure_tracing,
    instrument_app,
    record_rate_limit_rejection,
)
from .models import RequestAudit
from .quota import QuotaConfig, QuotaExceededError, consume_quota
from .rate_limit import RateLimiter
from .schemas import CalculationResponse, ExpressionRequest
from .security import AuthenticatedAPIKey, get_api_key

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
    app.state.quota_config = QuotaConfig(
        limit=settings.quota.limit,
        window_seconds=settings.quota.window_seconds,
    )
    await init_db(settings)
    app.state.grpc_channel = _create_grpc_channel(settings.evaluator)
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
    client_ip = request.client.host if request.client else "unknown"
    api_key_id = api_key.record.id
    rate_limiter_key: RateLimiter = app.state.rate_limit_key
    rate_limiter_ip: RateLimiter = app.state.rate_limit_ip
    expression_hash = payload.hash(api_key.raw_key)

    if not await rate_limiter_key.allow(str(api_key_id)):
        record_rate_limit_rejection("api_key")
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
        await _persist_audit(api_key_id, cache_key, payload.expression, client_ip, "cache_hit", 0.0)
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
        metadata = _build_grpc_metadata(request)
        with tracer.start_as_current_span(
            "gateway.grpc.evaluate",
            kind=SpanKind.CLIENT,
        ) as span:
            span.set_attribute("rpc.system", "grpc")
            span.set_attribute("rpc.service", "calculator.Evaluator")
            span.set_attribute("rpc.method", "Evaluate")
            span.set_attribute("net.peer.name", settings.evaluator.host)
            span.set_attribute("net.peer.port", settings.evaluator.port)
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


@app.get("/health/live")
async def live() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/health/ready")
async def ready() -> JSONResponse:
    return JSONResponse({"status": "ready"})


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


def _create_grpc_channel(evaluator: EvaluatorSettings) -> grpc.aio.Channel:
    target = f"{evaluator.host}:{evaluator.port}"
    if evaluator.use_tls:
        credentials = grpc.ssl_channel_credentials(
            root_certificates=_read_optional_bytes(evaluator.root_cert_path),
            private_key=_read_optional_bytes(evaluator.client_key_path),
            certificate_chain=_read_optional_bytes(evaluator.client_cert_path),
        )
        return grpc.aio.secure_channel(target, credentials)
    return grpc.aio.insecure_channel(target)


def _read_optional_bytes(path: Optional[Path]) -> Optional[bytes]:
    if path is None:
        return None
    resolved = Path(path).expanduser()
    if not resolved.exists():
        raise RuntimeError(f"gRPC credential file not found: {resolved}")
    return resolved.read_bytes()


def _build_grpc_metadata(request: Request) -> list[tuple[str, str]]:
    carrier: dict[str, str] = {}
    inject(carrier)
    metadata = list(carrier.items())
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        metadata.append(("x-request-id", request_id))
    return metadata
