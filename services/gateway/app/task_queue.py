"""Celery integration for distributing calculator jobs."""

from __future__ import annotations

import asyncio
import datetime as dt
import re
import threading
import time

from typing import Any, Coroutine, Dict, Mapping, Optional

from celery import Celery
from celery.utils.log import get_task_logger
from opentelemetry import trace
from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract
from opentelemetry.trace import Status, StatusCode
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

try:
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY
except ImportError:  # pragma: no cover - fallback for minimal environments
    class _Collector:
        def __init__(self, name: str, documentation: str, *, labelnames=(), namespace: str | None = None, **kwargs):
            self.name = f"{namespace}_{name}" if namespace else name
            self.labelnames = tuple(labelnames)
            self._values = {}

        def labels(self, **labels):
            key = tuple(labels.get(label) for label in self.labelnames)
            self._values.setdefault(key, 0.0)
            return self

        def inc(self, amount: float = 1.0):
            for key in list(self._values.keys()) or [tuple()]:
                self._values[key] = self._values.get(key, 0.0) + amount

        def dec(self, amount: float = 1.0):
            for key in list(self._values.keys()) or [tuple()]:
                self._values[key] = self._values.get(key, 0.0) - amount

        def set(self, value: float):
            for key in list(self._values.keys()) or [tuple()]:
                self._values[key] = value

        def observe(self, value: float):
            self.inc(value)

    class Counter(_Collector):
        pass

    class Gauge(_Collector):
        pass

    class Histogram(_Collector):
        pass

    class _Registry:
        def __init__(self):
            self._names_to_collectors = {}

    REGISTRY = _Registry()

from services.common.grpc import grpc
from services.protos import evaluator_pb2, evaluator_pb2_grpc

from .cache import JobCache, SymbolicResultCache
from .config import get_settings
from .evaluator_client import build_grpc_metadata, create_sync_channel
from .symbolic_client import SymbolicEngineClient, SymbolicEngineError
from .time_utils import utcnow
from .jobs import (
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    publish_job_update,
    serialize_job,
    upsert_symbolic_cache,
)
from .models import Job
from .database import get_engine

task_logger = get_task_logger(__name__)
tracer = trace.get_tracer(__name__)

settings = get_settings()

_METRIC_NAMESPACE = settings.observability.metrics_namespace


_symbolic_client: SymbolicEngineClient | None = None


def _register_metric(name: str, factory):
    full_name = f"{_METRIC_NAMESPACE}_{name}" if _METRIC_NAMESPACE else name
    try:
        return factory()
    except ValueError:
        existing = REGISTRY._names_to_collectors.get(full_name)  # type: ignore[attr-defined]
        if existing is None:
            raise
        return existing


_JOBS_ENQUEUED = _register_metric(
    "jobs_enqueued_total",
    lambda: Counter(
        "jobs_enqueued_total",
        "Total number of asynchronous calculator jobs submitted.",
        labelnames=("queue",),
        namespace=_METRIC_NAMESPACE,
    ),
)
_JOBS_IN_PROGRESS = _register_metric(
    "jobs_in_progress",
    lambda: Gauge(
        "jobs_in_progress",
        "Number of calculator jobs currently being processed by workers.",
        labelnames=("queue",),
        namespace=_METRIC_NAMESPACE,
    ),
)
_JOBS_FAILED = _register_metric(
    "jobs_failed_total",
    lambda: Counter(
        "jobs_failed_total",
        "Total number of calculator jobs that ultimately failed.",
        labelnames=("queue", "reason"),
        namespace=_METRIC_NAMESPACE,
    ),
)
_QUEUE_DEPTH = _register_metric(
    "job_queue_depth",
    lambda: Gauge(
        "job_queue_depth",
        "Depth of the Redis-backed Celery queue.",
        labelnames=("queue",),
        namespace=_METRIC_NAMESPACE,
    ),
)
_TASK_RUNTIME = _register_metric(
    "job_task_runtime_seconds",
    lambda: Histogram(
        "job_task_runtime_seconds",
        "Histogram of worker execution runtimes by outcome.",
        labelnames=("queue", "status"),
        namespace=_METRIC_NAMESPACE,
        buckets=(
            0.01,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
            30.0,
        ),
    ),
)
_QUEUE_WAIT = _register_metric(
    "job_queue_wait_seconds",
    lambda: Histogram(
        "job_queue_wait_seconds",
        "Time jobs spend waiting in the queue before worker execution.",
        labelnames=("queue",),
        namespace=_METRIC_NAMESPACE,
        buckets=(
            0.01,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
            30.0,
        ),
    ),
)

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


def _run_coroutine(coro: Coroutine[Any, Any, Any]):
    """Execute a coroutine regardless of surrounding event loop state."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list[Any] = []
    error: list[BaseException] = []

    def runner() -> None:
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()

    if error:
        raise error[0]
    return result[0]


def enqueue_job(
    job_id: str,
    *,
    queue_name: Optional[str] = None,
    trace_context: Optional[Dict[str, str]] = None,
) -> None:
    """Submit a job for asynchronous execution."""

    queue = queue_name or settings.job.queue_name
    headers = trace_context or {}
    signature = execute_job.s(job_id, queue_name=queue, trace_context=headers)
    signature.apply_async(
        queue=queue,
        routing_key=queue,
        headers=headers,
    )
    _record_job_enqueued(queue)
    _schedule_queue_depth_refresh(queue)


@celery_app.task(
    bind=True,
    name="gateway.execute_job",
    autoretry_for=(TransientJobError,),
    retry_backoff=settings.job.retry_backoff_seconds,
    retry_jitter=True,
    retry_kwargs={"max_retries": settings.job.max_retries},
)
def execute_job(
    self,
    job_id: str,
    queue_name: Optional[str] = None,
    trace_context: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Celery task entry point that coordinates job execution."""

    parent_context = extract(trace_context or {})
    token = attach(parent_context)
    try:
        return _run_coroutine(
            _execute_job(
                job_id,
                queue_name=queue_name,
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
    queue_name: Optional[str],
    trace_headers: Mapping[str, str],
    attempt: int,
    max_retries: int,
) -> Dict[str, Any]:
    start_time = time.perf_counter()
    redis = Redis.from_url(settings.redis.url, decode_responses=True)
    cache = JobCache(redis, settings.job.default_ttl_seconds, namespace=settings.job.cache_namespace)
    symbolic_cache = SymbolicResultCache(
        redis,
        settings.symbolic.cache_ttl_seconds,
        namespace=settings.symbolic.cache_namespace,
    )
    engine = await get_engine(settings)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    resolved_queue = queue_name or settings.job.queue_name

    try:
        async with session_factory() as session:
            job = await _lock_job(session, job_id)
            if job is None:
                task_logger.warning("Job %s not found", job_id)
                await _refresh_queue_depth(redis, resolved_queue)
                return {"status": "missing"}

            if job.queue_name:
                resolved_queue = job.queue_name

            in_progress_metric = _JOBS_IN_PROGRESS.labels(queue=resolved_queue)
            in_progress_metric.inc()
            try:
                queue_depth_before = await _refresh_queue_depth(redis, resolved_queue)
                with tracer.start_as_current_span(
                    "worker.job",
                    attributes={
                        "job.id": job_id,
                        "job.queue_depth_start": queue_depth_before,
                        "job.queue_name": resolved_queue,
                    },
                ) as span:
                    span.set_attribute("job.attempt", attempt)
                    span.set_attribute("job.max_retries", max_retries)
                    queue_wait_ms = _compute_queue_wait_ms(job)
                    if queue_wait_ms is not None:
                        span.set_attribute("job.queue_wait_ms", queue_wait_ms)
                        _QUEUE_WAIT.labels(queue=resolved_queue).observe(queue_wait_ms / 1000.0)

                    await _mark_running(session, job, cache, redis)

                    try:
                        if job.mode == "symbolic":
                            (
                                result_payload,
                                cache_request_payload,
                                verification_passed,
                                verification_error,
                            ) = await _process_symbolic_job(job)
                            status = STATUS_SUCCEEDED
                            job.verification_passed = verification_passed
                            job.verification_error = verification_error
                            await _finalize_job(
                                session,
                                job,
                                cache,
                                redis,
                                status=status,
                                payload=result_payload,
                            )
                            if job.symbolic_cache_key:
                                await upsert_symbolic_cache(
                                    session,
                                    cache_key=job.symbolic_cache_key,
                                    request_payload=cache_request_payload,
                                    result_payload=result_payload,
                                    verification_passed=verification_passed,
                                    verification_error=verification_error,
                                )
                                await symbolic_cache.set(job.symbolic_cache_key, result_payload)
                        else:
                            response = await _invoke_evaluator(job, trace_headers)
                            result_payload = _build_result_payload(response)
                            status = (
                                STATUS_SUCCEEDED
                                if result_payload.get("value") is not None
                                else STATUS_FAILED
                            )
                            await _finalize_job(
                                session,
                                job,
                                cache,
                                redis,
                                status=status,
                                payload=result_payload,
                            )
                            if status == STATUS_FAILED:
                                _record_job_failure(
                                    resolved_queue, result_payload.get("error") or "evaluator_error"
                                )
                        span.set_attribute("job.status", status)
                        span.set_status(Status(StatusCode.OK))
                        duration_ms = (time.perf_counter() - start_time) * 1000.0
                        span.set_attribute("job.duration_ms", duration_ms)
                        queue_depth_after = await _refresh_queue_depth(redis, resolved_queue)
                        span.set_attribute("job.queue_depth_end", queue_depth_after)
                        _observe_task_runtime(resolved_queue, status, duration_ms)
                        return {
                            "status": status,
                            "result": result_payload,
                            "duration_ms": duration_ms,
                        }
                    except grpc.RpcError as exc:
                        try:
                            return await _handle_grpc_failure(
                                session,
                                job,
                                cache,
                                redis,
                                exc,
                                queue_name=resolved_queue,
                                attempt=attempt,
                                max_retries=max_retries,
                            )
                        finally:
                            queue_depth_after = await _refresh_queue_depth(redis, resolved_queue)
                            span.set_attribute("job.queue_depth_end", queue_depth_after)
                    except TransientJobError as exc:
                        duration_ms = (time.perf_counter() - start_time) * 1000.0
                        span.set_attribute("job.status", STATUS_QUEUED)
                        span.set_attribute("job.duration_ms", duration_ms)
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR))
                        queue_depth_after = await _refresh_queue_depth(redis, resolved_queue)
                        span.set_attribute("job.queue_depth_end", queue_depth_after)
                        raise
                    except JobExecutionError as exc:
                        duration_ms = (time.perf_counter() - start_time) * 1000.0
                        span.set_attribute("job.status", STATUS_FAILED)
                        span.set_attribute("job.duration_ms", duration_ms)
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR))
                        queue_depth_after = await _refresh_queue_depth(redis, resolved_queue)
                        span.set_attribute("job.queue_depth_end", queue_depth_after)
                        _record_job_failure(resolved_queue, exc)
                        _observe_task_runtime(resolved_queue, STATUS_FAILED, duration_ms)
                        raise
                    except Exception as exc:  # noqa: BLE001
                        duration_ms = (time.perf_counter() - start_time) * 1000.0
                        span.set_attribute("job.status", STATUS_FAILED)
                        span.set_attribute("job.duration_ms", duration_ms)
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR))
                        queue_depth_after = await _refresh_queue_depth(redis, resolved_queue)
                        span.set_attribute("job.queue_depth_end", queue_depth_after)
                        _record_job_failure(resolved_queue, exc)
                        _observe_task_runtime(resolved_queue, STATUS_FAILED, duration_ms)
                        await _mark_failed(session, job, cache, redis, str(exc))
                        raise JobExecutionError(str(exc)) from exc
            finally:
                in_progress_metric.dec()
    finally:
        await redis.close()


async def _lock_job(session, job_id: str) -> Optional[Job]:
    stmt = select(Job).where(Job.id == job_id).with_for_update()
    result = await session.execute(stmt)
    return result.scalars().first()


async def _mark_running(session, job: Job, cache: JobCache, redis: Redis) -> None:
    job.status = STATUS_RUNNING
    job.started_at = utcnow()
    job.completed_at = None
    job.error = None
    await session.commit()
    await _cache_and_publish(job, cache, redis)


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
    redis: Redis,
    exc: grpc.RpcError,
    *,
    queue_name: str,
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
        await _cache_and_publish(job, cache, redis)
        raise TransientJobError(detail) from exc

    await _mark_failed(session, job, cache, redis, detail)
    _record_job_failure(queue_name, detail)
    raise JobExecutionError(detail) from exc


async def _mark_failed(session, job: Job, cache: JobCache, redis: Redis, error: str) -> None:
    job.status = STATUS_FAILED
    job.completed_at = utcnow()
    job.error = error
    job.result_payload = None
    await session.commit()
    await _cache_and_publish(job, cache, redis)


async def _finalize_job(
    session,
    job: Job,
    cache: JobCache,
    redis: Redis,
    *,
    status: str,
    payload: Dict[str, Any],
) -> None:
    job.status = status
    job.completed_at = utcnow()
    job.result_payload = payload if status == STATUS_SUCCEEDED else None
    job.error = None if status == STATUS_SUCCEEDED else payload.get("error")
    await session.commit()
    await _cache_and_publish(job, cache, redis)


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


async def _cache_and_publish(job: Job, cache: JobCache, redis: Redis) -> Dict[str, Any]:
    payload = serialize_job(job, settings)
    await cache.set(job.id, payload)
    await publish_job_update(redis, job.id, payload, settings=settings)
    return payload


def _get_symbolic_client() -> SymbolicEngineClient:
    global _symbolic_client
    if _symbolic_client is None:
        _symbolic_client = SymbolicEngineClient(settings.symbolic)
    return _symbolic_client


async def _process_symbolic_job(
    job: Job
) -> tuple[Dict[str, Any], Dict[str, Any], Optional[bool], Optional[str]]:
    client = _get_symbolic_client()
    request_payload = dict(job.symbolic_payload or {})
    if not request_payload:
        request_payload = {
            "operation": "simplify",
            "expression": job.input_expression,
            "context": {"variables": job.context},
        }
    request_payload.setdefault("expression", job.input_expression)

    try:
        result = await asyncio.to_thread(client.compute_sync, request_payload)
    except SymbolicEngineError as exc:
        raise JobExecutionError(str(exc)) from exc

    verification_passed, verification_error = await _verify_symbolic_result(
        job, result, request_payload
    )
    metadata = result.setdefault("metadata", {})
    metadata["verification"] = {"passed": verification_passed, "error": verification_error}
    return result, request_payload, verification_passed, verification_error


async def _verify_symbolic_result(
    job: Job, result_payload: Dict[str, Any], request_payload: Dict[str, Any]
) -> tuple[Optional[bool], Optional[str]]:
    context_payload = request_payload.get("context") or {}
    variables = context_payload.get("variables") or {}
    if not isinstance(variables, dict) or not variables:
        return None, None

    numeric_context: Dict[str, float] = {}
    for key, value in variables.items():
        try:
            numeric_context[str(key)] = float(value)
        except (TypeError, ValueError):
            return None, "non_numeric_context"

    canonical_expr = (result_payload.get("result") or {}).get("canonical")
    if not canonical_expr:
        return None, "missing_canonical"

    original_value = await _evaluate_expression(job.input_expression, numeric_context)
    canonical_value = await _evaluate_expression(canonical_expr, numeric_context)
    if original_value is None or canonical_value is None:
        return None, "verification_eval_failed"

    tolerance = max(1.0, abs(original_value)) * 1e-6
    if abs(original_value - canonical_value) <= tolerance:
        return True, None
    error_message = f"mismatch({original_value:.8f},{canonical_value:.8f})"
    return False, error_message[:255]


async def _evaluate_expression(expression: str, context: Dict[str, float]) -> Optional[float]:
    stub = _get_sync_stub()
    request = evaluator_pb2.EvaluateRequest(
        expression=expression, context={k: str(v) for k, v in context.items()}
    )
    deadline = settings.evaluator.deadline_ms / 1000.0
    try:
        response = await asyncio.to_thread(
            stub.Evaluate,
            request,
            timeout=deadline,
            metadata=build_grpc_metadata(),
        )
    except grpc.RpcError:
        return None
    if response.WhichOneof("result") == "value":
        return response.value
    return None



def _record_job_enqueued(queue_name: str) -> None:
    _JOBS_ENQUEUED.labels(queue=queue_name).inc()


def _observe_task_runtime(queue_name: str, status: str, duration_ms: float) -> None:
    _TASK_RUNTIME.labels(queue=queue_name, status=status).observe(duration_ms / 1000.0)


def _record_job_failure(queue_name: str, reason: Exception | str) -> None:
    label = _normalize_failure_reason(reason)
    _JOBS_FAILED.labels(queue=queue_name, reason=label).inc()


def _normalize_failure_reason(reason: Exception | str) -> str:
    if isinstance(reason, Exception):
        detail = str(reason).strip()
        if detail:
            text = detail
        else:
            text = reason.__class__.__name__
    else:
        text = str(reason).strip()
    if not text:
        text = "unknown"
    sanitized = text.lower().replace(" ", "_")
    sanitized = re.sub(r"[^a-z0-9_\-\.]+", "_", sanitized)
    sanitized = sanitized.strip("_") or "unknown"
    return sanitized[:64]


def _compute_queue_wait_ms(job: Job) -> Optional[float]:
    created_at = job.created_at
    if not created_at:
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=dt.timezone.utc)
    now = dt.datetime.now(dt.timezone.utc)
    wait_seconds = max((now - created_at).total_seconds(), 0.0)
    return wait_seconds * 1000.0


async def _refresh_queue_depth(redis: Redis, queue_name: Optional[str] = None) -> int:
    if not hasattr(redis, "llen"):
        return 0
    target = queue_name or settings.job.queue_name
    keys_to_check = [f"queue:{target}", target, f"{target}-applied"]
    depth = 0
    for key in keys_to_check:
        try:
            value = await redis.llen(key)
        except Exception:  # noqa: BLE001
            continue
        if value:
            depth = int(value)
            break
    _QUEUE_DEPTH.labels(queue=target).set(depth)
    return depth


def _schedule_queue_depth_refresh(queue_name: Optional[str] = None) -> None:
    async def _update() -> None:
        redis = Redis.from_url(settings.redis.url, decode_responses=True)
        try:
            await _refresh_queue_depth(redis, queue_name)
        except Exception as exc:  # noqa: BLE001
            task_logger.debug("Queue depth refresh failed: %s", exc)
        finally:
            await redis.close()

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_update())
    else:
        loop.create_task(_update())

