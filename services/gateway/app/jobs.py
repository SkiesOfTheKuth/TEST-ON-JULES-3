"""Utilities for creating and serializing asynchronous jobs."""

from __future__ import annotations

import uuid
import json
from typing import Any, Dict, Iterable, Optional

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .cache import JobCache
from .config import GatewaySettings
from .models import Job
from .schemas import JobResultResponse, JobSubmissionRequest

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"


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
) -> Job:
    job = Job(
        id=str(uuid.uuid4()),
        status=STATUS_QUEUED,
        input_expression=submission.input_expression,
        context=submission.context,
        result_payload=None,
        error=None,
        priority=normalize_priority(submission.priority, levels=settings.job.priority_levels),
        tags=_deduplicate_tags(submission.tags),
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
    response = JobResultResponse.model_validate(job, from_attributes=True)
    if include_links:
        response.links = build_job_links(settings, job.id)
    return response.model_dump(mode="json")


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

