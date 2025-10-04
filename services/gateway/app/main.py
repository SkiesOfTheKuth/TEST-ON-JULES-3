"""FastAPI application for the calculator gateway."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import grpc
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from services.protos import evaluator_pb2, evaluator_pb2_grpc

from .cache import ResultCache
from .config import get_settings
from .database import get_session, init_db
from .instrumentation import configure_tracing, instrument_app
from .models import RequestAudit
from .rate_limit import RateLimiter
from .schemas import CalculationResponse, ExpressionRequest
from .security import get_api_key

logger = logging.getLogger(__name__)

settings = get_settings()
configure_tracing(settings)
app = FastAPI(title="Calculator Gateway", version="1.0.0")
instrument_app(app, settings)


@app.on_event("startup")
async def startup_event() -> None:
    app.state.settings = settings
    app.state.redis = Redis.from_url(settings.redis.url, decode_responses=True)
    app.state.cache = ResultCache(app.state.redis, settings.redis.cache_ttl_seconds)
    app.state.rate_limit_key = RateLimiter(
        app.state.redis,
        settings.redis.rate_limit_requests,
        settings.redis.rate_limit_window_seconds,
        "rate:key",
    )
    app.state.rate_limit_ip = RateLimiter(
        app.state.redis,
        settings.redis.rate_limit_requests * 2,
        settings.redis.rate_limit_window_seconds,
        "rate:ip",
    )
    await init_db(settings)
    app.state.grpc_channel = grpc.aio.insecure_channel(f"{settings.evaluator.host}:{settings.evaluator.port}")
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
) -> Any:
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
    api_key=Depends(require_api_key),
) -> CalculationResponse:
    client_ip = request.client.host if request.client else "unknown"
    rate_limiter_key: RateLimiter = app.state.rate_limit_key
    rate_limiter_ip: RateLimiter = app.state.rate_limit_ip
    if not await rate_limiter_key.allow(str(api_key.id)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="API key rate limit exceeded")
    if not await rate_limiter_ip.allow(client_ip):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="IP rate limit exceeded")

    cache: ResultCache = app.state.cache
    cache_key = payload.hash(str(api_key.id))
    cached_value = await cache.get(cache_key) if settings.cache_pure_results else None
    if cached_value is not None:
        await _persist_audit(api_key.id, cache_key, payload.expression, client_ip, "cache", 0.0)
        return CalculationResponse(
            expression=payload.expression,
            value=cached_value,
            duration_ms=0.0,
            from_cache=True,
        )

    stub: evaluator_pb2_grpc.EvaluatorStub = app.state.grpc_stub
    request_message = evaluator_pb2.EvaluateRequest(expression=payload.expression, context={k: str(v) for k, v in payload.context.items()})

    try:
        response = await stub.Evaluate(
            request_message,
            timeout=settings.evaluator.deadline_ms / 1000,
        )
    except grpc.AioRpcError as exc:
        logger.exception("Evaluator call failed")
        status_code = exc.code()
        if status_code == grpc.StatusCode.INVALID_ARGUMENT:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.details())
        if status_code == grpc.StatusCode.RESOURCE_EXHAUSTED:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Evaluator busy")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Evaluator unavailable")

    asyncio.create_task(
        _persist_audit(
            api_key.id,
            cache_key,
            payload.expression,
            client_ip,
            "success",
            response.duration_ms,
        )
    )

    if settings.cache_pure_results:
        await cache.set(cache_key, response.value)

    return CalculationResponse(
        expression=payload.expression,
        value=response.value,
        duration_ms=response.duration_ms,
        from_cache=False,
    )


@app.post("/calculate", response_model=CalculationResponse)
async def calculate(payload: ExpressionRequest, request: Request, api_key=Depends(require_api_key)) -> CalculationResponse:
    return await calculate_sync(payload, request, api_key)


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
