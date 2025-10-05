"""Utilities for creating and serializing asynchronous jobs."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .cache import JobCache
from .config import GatewaySettings
from .models import Job
from .schemas import JobPolicyStatus, JobResultResponse, JobSubmissionRequest

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
    assigned_priority: Optional[int] = None
    requested_priority: Optional[int] = None


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
        status=STATUS_QUEUED,
        input_expression=submission.input_expression,
        context=submission.context,
        result_payload=None,
        error=None,
        requested_priority=requested_priority,
        priority=normalized_priority,
        tags=_deduplicate_tags(submission.tags),
        queue_name=metadata.queue_name,
        task_type=metadata.task_type,
        policy_snapshot=dict(metadata.policy_snapshot),
        policy_violations=list(metadata.policy_violations),
        policy_enforced=bool(metadata.policy_enforced),
        estimated_runtime_ms=metadata.estimated_runtime_ms,
    )
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


