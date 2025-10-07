"""Utilities for creating and serializing asynchronous jobs."""

from __future__ import annotations

import json
import uuid
import hashlib
import datetime as dt
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .cache import JobCache
from .config import GatewaySettings
from .models import Job, SymbolicCacheEntry
from .schemas import JobPolicyStatus, JobResultResponse, JobSubmissionRequest, SymbolicJobRequest

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"


@dataclass(slots=True)
class JobCreationMetadata:
    tenant: str
    queue_name: str
    task_type: str
    policy_snapshot: Dict[str, Any]
    policy_violations: list[str]
    policy_enforced: bool
    estimated_runtime_ms: Optional[int]
    mode: str = "arithmetic"
    symbolic_payload: Optional[Dict[str, Any]] = None
    symbolic_cache_key: Optional[str] = None
    assigned_priority: Optional[int] = None
    requested_priority: Optional[int] = None
    initial_status: str = STATUS_QUEUED
    initial_result: Optional[Dict[str, Any]] = None
    initial_error: Optional[str] = None
    verification_passed: Optional[bool] = None
    verification_error: Optional[str] = None


def normalize_priority(priority: int, *, levels: int) -> int:
    if levels <= 0:
        return 0
    maximum = max(levels - 1, 0)
    return max(0, min(priority, maximum))


async def count_queued_jobs(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(Job).where(Job.status == STATUS_QUEUED)
    result = await session.execute(stmt)
    return int(result.scalar_one())


async def create_job(
    session: AsyncSession,
    submission: JobSubmissionRequest,
    *,
    settings: GatewaySettings,
    metadata: JobCreationMetadata,
) -> Job:
    requested_priority = (
        metadata.requested_priority if metadata.requested_priority is not None else submission.priority
    )
    normalized_priority = normalize_priority(
        metadata.assigned_priority if metadata.assigned_priority is not None else submission.priority,
        levels=settings.job.priority_levels,
    )

    job = Job(
        id=str(uuid.uuid4()),
        tenant=metadata.tenant,
        status=metadata.initial_status,
        input_expression=submission.input_expression,
        context=submission.context,
        result_payload=metadata.initial_result,
        error=metadata.initial_error,
        requested_priority=requested_priority,
        priority=normalized_priority,
        tags=_deduplicate_tags(submission.tags),
        queue_name=metadata.queue_name,
        task_type=metadata.task_type,
        mode=metadata.mode,
        symbolic_payload=metadata.symbolic_payload,
        symbolic_cache_key=metadata.symbolic_cache_key,
        verification_passed=metadata.verification_passed,
        verification_error=metadata.verification_error,
        policy_snapshot=dict(metadata.policy_snapshot),
        policy_violations=list(metadata.policy_violations),
        policy_enforced=bool(metadata.policy_enforced),
        estimated_runtime_ms=metadata.estimated_runtime_ms,
    )
    if metadata.initial_status != STATUS_QUEUED:
        now = dt.datetime.utcnow()
        job.started_at = now
        job.completed_at = now
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def fetch_job(session: AsyncSession, job_id: str) -> Optional[Job]:
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    return result.scalars().first()


def serialize_job(job: Job, settings: GatewaySettings, *, include_links: bool = True) -> Dict[str, Any]:
    payload = JobResultResponse(
        id=job.id,
        tenant=job.tenant,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        priority=job.priority,
        requested_priority=job.requested_priority,
        tags=job.tags,
        queue_name=job.queue_name,
        task_type=job.task_type,
        mode=job.mode,
        symbolic_cache_key=job.symbolic_cache_key,
        symbolic_request=job.symbolic_payload,
        verification_passed=job.verification_passed,
        verification_error=job.verification_error,
        estimated_runtime_ms=job.estimated_runtime_ms,
        policy=JobPolicyStatus(
            enforced=job.policy_enforced,
            violations=job.policy_violations,
            snapshot=job.policy_snapshot,
        ),
        links=build_job_links(settings, job.id) if include_links else {},
        result_payload=job.result_payload,
        error=job.error,
    )
    return payload.model_dump(mode="json")


def build_job_links(settings: GatewaySettings, job_id: str) -> Dict[str, str]:
    base = f"/jobs/{job_id}"
    return {
        "self": base,
        "poll": base,
        "result": base,
        "ws": f"/ws/jobs/{job_id}",
    }


async def write_job_cache(cache: JobCache, job: Job, settings: GatewaySettings) -> None:
    await cache.set(job.id, serialize_job(job, settings))


def build_job_channel(settings: GatewaySettings, job_id: str) -> str:
    namespace = settings.job.notification_namespace
    return f"{namespace}:{job_id}" if namespace else job_id


async def publish_job_update(
    redis: Redis, job_id: str, payload: Dict[str, Any], *, settings: GatewaySettings
) -> None:
    channel = build_job_channel(settings, job_id)
    message = json.dumps(payload)
    try:
        await redis.publish(channel, message)
    except Exception:  # noqa: BLE001 - redis connection issues should not break workers
        return


def _deduplicate_tags(tags: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for raw in tags:
        if not isinstance(raw, str):
            continue
        candidate = raw.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(candidate)
        if len(normalized) >= 32:
            break
    return normalized



def symbolic_request_to_payload(request: SymbolicJobRequest | Dict[str, Any] | None) -> Dict[str, Any]:
    if request is None:
        return {}
    if isinstance(request, SymbolicJobRequest):
        return request.model_dump(mode="json", exclude_none=True)
    if isinstance(request, dict):
        return request
    raise TypeError(f"Unsupported symbolic request type: {type(request)!r}")


def build_symbolic_cache_key(tenant: str, request: SymbolicJobRequest) -> str:
    payload = symbolic_request_to_payload(request)
    digest = hashlib.sha256()
    digest.update(tenant.encode("utf-8"))
    digest.update(json.dumps(payload, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


async def fetch_symbolic_cache_entry(session: AsyncSession, cache_key: str) -> Optional[SymbolicCacheEntry]:
    stmt = select(SymbolicCacheEntry).where(SymbolicCacheEntry.expression_hash == cache_key)
    result = await session.execute(stmt)
    return result.scalars().first()


async def load_symbolic_cache(session: AsyncSession, cache_key: str) -> Optional[Dict[str, Any]]:
    entry = await fetch_symbolic_cache_entry(session, cache_key)
    if entry is None:
        return None
    return entry.result_payload


async def upsert_symbolic_cache(
    session: AsyncSession,
    *,
    cache_key: str,
    request_payload: Dict[str, Any],
    result_payload: Dict[str, Any],
    verification_passed: Optional[bool],
    verification_error: Optional[str],
) -> SymbolicCacheEntry:
    entry = await fetch_symbolic_cache_entry(session, cache_key)
    timestamp = dt.datetime.utcnow()
    if entry is None:
        entry = SymbolicCacheEntry(
            expression_hash=cache_key,
            request_payload=request_payload,
            result_payload=result_payload,
            verification_passed=verification_passed,
            verification_error=verification_error,
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(entry)
    else:
        entry.request_payload = request_payload
        entry.result_payload = result_payload
        entry.verification_passed = verification_passed
        entry.verification_error = verification_error
        entry.updated_at = timestamp
    await session.commit()
    await session.refresh(entry)
    return entry
