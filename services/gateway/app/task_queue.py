"""Celery integration for distributing calculator jobs."""

from __future__ import annotations

import asyncio
import time
import datetime as dt
from typing import Any, Dict, Mapping, Optional

from celery import Celery
from celery.utils.log import get_task_logger
from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract
from opentelemetry.trace import Status, StatusCode
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from services.common.grpc import grpc
from services.protos import evaluator_pb2, evaluator_pb2_grpc

from .cache import JobCache
from .config import get_settings
from .evaluator_client import build_grpc_metadata, create_sync_channel
from .jobs import (
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    serialize_job,
)
from .models import Job
from .database import get_engine

task_logger = get_task_logger(__name__)
tracer = trace.get_tracer(__name__)

settings = get_settings()

celery_app = Celery("calculator-gateway")
celery_app.conf.update(
    broker_url=settings.redis.url,
    result_backend=settings.redis.url,
    task_default_queue=settings.job.queue_name,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


class TransientJobError(Exception):
    """Raised to signal Celery that the job should be retried."""


class JobExecutionError(Exception):
    """Raised when the job ultimately fails."""


_sync_channel = None
_sync_stub: Optional[evaluator_pb2_grpc.EvaluatorStub] = None


def enqueue_job(job_id: str, *, trace_context: Optional[Dict[str, str]] = None) -> None:
    """Submit a job for asynchronous execution."""

    celery_app.send_task(
        name="gateway.execute_job",
        args=[job_id],
        kwargs={"trace_context": trace_context or {}},
        queue=settings.job.queue_name,
    )


@celery_app.task(
    bind=True,
    name="gateway.execute_job",
    autoretry_for=(TransientJobError,),
    retry_backoff=settings.job.retry_backoff_seconds,
    retry_jitter=True,
    retry_kwargs={"max_retries": settings.job.max_retries},
)
def execute_job(self, job_id: str, trace_context: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Celery task entry point that coordinates job execution."""

    parent_context = extract(trace_context or {})
    token = attach(parent_context)
    try:
        return asyncio.run(
            _execute_job(
                job_id,
                trace_headers=trace_context or {},
                attempt=self.request.retries,
                max_retries=self.max_retries or settings.job.max_retries,
            )
        )
    finally:
        detach(token)


async def _execute_job(
    job_id: str,
    *,
    trace_headers: Mapping[str, str],
    attempt: int,
    max_retries: int,
) -> Dict[str, Any]:
    start_time = time.perf_counter()
    redis = Redis.from_url(settings.redis.url, decode_responses=True)
    cache = JobCache(redis, settings.job.default_ttl_seconds, namespace=settings.job.cache_namespace)
    engine = await get_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as session:
            job = await _lock_job(session, job_id)
            if job is None:
                task_logger.warning("Job %s not found", job_id)
                return {"status": "missing"}

            with tracer.start_as_current_span("worker.job", attributes={"job.id": job_id}) as span:
                span.set_attribute("job.attempt", attempt)
                span.set_attribute("job.max_retries", max_retries)
                await _mark_running(session, job, cache)

                try:
                    response = await _invoke_evaluator(job, trace_headers)
                except grpc.RpcError as exc:
                    return await _handle_grpc_failure(
                        session,
                        job,
                        cache,
                        exc,
                        attempt=attempt,
                        max_retries=max_retries,
                    )
                except Exception as exc:  # noqa: BLE001
                    await _mark_failed(session, job, cache, str(exc))
                    raise JobExecutionError(str(exc)) from exc

                result_payload = _build_result_payload(response)
                status = STATUS_SUCCEEDED if result_payload.get("value") is not None else STATUS_FAILED
                await _finalize_job(session, job, cache, status=status, payload=result_payload)
                span.set_attribute("job.status", status)
                span.set_status(Status(StatusCode.OK))
                duration_ms = (time.perf_counter() - start_time) * 1000.0
                span.set_attribute("job.duration_ms", duration_ms)
                return {
                    "status": status,
                    "result": result_payload,
                    "duration_ms": duration_ms,
                }
    finally:
        await redis.close()


async def _lock_job(session, job_id: str) -> Optional[Job]:
    stmt = select(Job).where(Job.id == job_id).with_for_update()
    result = await session.execute(stmt)
    return result.scalars().first()


async def _mark_running(session, job: Job, cache: JobCache) -> None:
    job.status = STATUS_RUNNING
    job.started_at = dt.datetime.utcnow()
    job.completed_at = None
    job.error = None
    await session.commit()
    await cache.set(job.id, serialize_job(job, settings))


async def _invoke_evaluator(job: Job, trace_headers: Mapping[str, str]):
    stub = _get_sync_stub()
    request = evaluator_pb2.EvaluateRequest(
        expression=job.input_expression,
        context={k: str(v) for k, v in job.context.items()},
    )
    metadata = build_grpc_metadata(extra=dict(trace_headers))
    deadline = settings.evaluator.deadline_ms / 1000.0

    with tracer.start_as_current_span(
        "worker.job.evaluate",
        attributes={"job.id": job.id, "rpc.method": "Evaluate"},
    ):
        return await asyncio.to_thread(
            stub.Evaluate,
            request,
            timeout=deadline,
            metadata=metadata,
        )


async def _handle_grpc_failure(
    session,
    job: Job,
    cache: JobCache,
    exc: grpc.RpcError,
    *,
    attempt: int,
    max_retries: int,
) -> Dict[str, Any]:
    status_code = exc.code() if hasattr(exc, "code") else None
    detail = exc.details() if hasattr(exc, "details") else None
    if not detail and status_code is not None:
        detail = status_code.name
    if not detail:
        detail = exc.__class__.__name__
    task_logger.warning(
        "Evaluator RPC failed for job %s: %s", job.id, detail, exc_info=exc if status_code is None else None
    )

    if status_code in {
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.RESOURCE_EXHAUSTED,
    } and attempt < max_retries:
        job.status = STATUS_QUEUED
        job.started_at = None
        job.completed_at = None
        job.error = detail
        await session.commit()
        await cache.set(job.id, serialize_job(job, settings))
        raise TransientJobError(detail) from exc

    await _mark_failed(session, job, cache, detail)
    raise JobExecutionError(detail) from exc


async def _mark_failed(session, job: Job, cache: JobCache, error: str) -> None:
    job.status = STATUS_FAILED
    job.completed_at = dt.datetime.utcnow()
    job.error = error
    job.result_payload = None
    await session.commit()
    await cache.set(job.id, serialize_job(job, settings))


async def _finalize_job(
    session,
    job: Job,
    cache: JobCache,
    *,
    status: str,
    payload: Dict[str, Any],
) -> None:
    job.status = status
    job.completed_at = dt.datetime.utcnow()
    job.result_payload = payload if status == STATUS_SUCCEEDED else None
    job.error = None if status == STATUS_SUCCEEDED else payload.get("error")
    await session.commit()
    await cache.set(job.id, serialize_job(job, settings))


def _build_result_payload(response: evaluator_pb2.EvaluateResponse) -> Dict[str, Any]:
    if response.WhichOneof("result") == "error":
        return {"error": response.error, "duration_ms": response.duration_ms}
    return {"value": response.value, "duration_ms": response.duration_ms}


def _get_sync_stub() -> evaluator_pb2_grpc.EvaluatorStub:
    global _sync_channel, _sync_stub
    if _sync_stub is None:
        _sync_channel = create_sync_channel(settings.evaluator)
        _sync_stub = evaluator_pb2_grpc.EvaluatorStub(_sync_channel)
    return _sync_stub

