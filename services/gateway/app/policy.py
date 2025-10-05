"""Policy evaluation utilities for job queue governance."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

from opentelemetry import trace
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import GatewaySettings
from .models import TenantPolicy
from .quota import QuotaConfig
from .schemas import JobSubmissionRequest

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass(slots=True)
class PolicyDecision:
    tenant: str
    allowed: bool
    queue_name: str
    task_type: str
    normalized_priority: int
    requested_priority: int
    estimated_runtime_ms: Optional[int]
    violations: list[str]
    snapshot: Dict[str, Any]
    policy_enforced: bool
    quota_config: QuotaConfig
    denial_reason: Optional[str] = None


async def evaluate_job_policy(
    session: AsyncSession,
    redis: Redis,
    *,
    tenant: str,
    submission: JobSubmissionRequest,
    settings: GatewaySettings,
    base_quota: QuotaConfig,
) -> PolicyDecision:
    """Evaluate policy constraints for an incoming job submission."""

    queue_map = _queue_map(settings)
    requested_lane, lane_reason = _classify_lane(submission, settings)
    requested_queue = queue_map[requested_lane]
    estimated_runtime_ms = submission.estimated_runtime_ms or _estimate_runtime(submission)
    requested_priority = max(submission.priority, 0)

    with tracer.start_as_current_span("policy.evaluate_job") as span:
        span.set_attribute("tenant.id", tenant)
        span.set_attribute("job.requested_lane", requested_lane)
        span.set_attribute("job.requested_queue", requested_queue)
        span.set_attribute("job.requested_priority", requested_priority)
        if estimated_runtime_ms is not None:
            span.set_attribute("job.estimated_runtime_ms", estimated_runtime_ms)

        policy_dict, policy_source = await _load_policy(session, redis, tenant, settings, queue_map)
        allowed_queues = set(policy_dict.get("allowed_queues") or queue_map.values())
        if not allowed_queues:
            allowed_queues = set(queue_map.values())

        max_runtime_ms = policy_dict.get("max_runtime_ms") or settings.job.default_max_runtime_ms
        max_priority = policy_dict.get("max_priority")
        if max_priority is None:
            max_priority = settings.job.priority_levels - 1
        else:
            max_priority = max(0, min(max_priority, settings.job.priority_levels - 1))

        normalized_priority = min(requested_priority, max_priority)
        policy_enforced = normalized_priority != requested_priority

        violations: list[str] = []
        hard_failures: list[str] = []
        resolved_lane = requested_lane
        resolved_queue = requested_queue

        if policy_dict.get("banned_patterns"):
            for pattern in policy_dict["banned_patterns"]:
                try:
                    if re.search(pattern, submission.input_expression, re.IGNORECASE):
                        violation = f"banned_operation:{pattern}"
                        violations.append(violation)
                        hard_failures.append(violation)
                except re.error:
                    logger.warning("Invalid policy regex for tenant %s: %s", tenant, pattern)

        if max_runtime_ms and estimated_runtime_ms and estimated_runtime_ms > max_runtime_ms:
            violation = "runtime_limit_exceeded"
            violations.append(violation)
            hard_failures.append(violation)

        allow_heavy = bool(policy_dict.get("allow_heavy", True))
        allow_gpu = bool(policy_dict.get("allow_gpu", False))

        if resolved_queue not in allowed_queues:
            violations.append(f"queue_disallowed:{resolved_lane}")
            fallback_lane = _select_fallback_lane(allowed_queues, queue_map, prefer_gpu=allow_gpu)
            if fallback_lane is None:
                hard_failures.append("queue_disallowed")
            else:
                policy_enforced = True
                resolved_lane = fallback_lane
                resolved_queue = queue_map[fallback_lane]

        if resolved_lane == "gpu" and not allow_gpu:
            violations.append("gpu_lane_blocked")
            if submission.requires_gpu:
                hard_failures.append("gpu_required_but_blocked")
            else:
                fallback_lane = "heavy" if allow_heavy and queue_map["heavy"] in allowed_queues else "standard"
                if queue_map[fallback_lane] in allowed_queues:
                    policy_enforced = True
                    resolved_lane = fallback_lane
                    resolved_queue = queue_map[fallback_lane]
                else:
                    hard_failures.append("gpu_lane_unavailable")

        if resolved_lane == "heavy" and not allow_heavy:
            violations.append("heavy_lane_blocked")
            if queue_map["standard"] in allowed_queues:
                policy_enforced = True
                resolved_lane = "standard"
                resolved_queue = queue_map["standard"]
            else:
                hard_failures.append("heavy_lane_unavailable")

        quota_config = base_quota
        quota_limit = policy_dict.get("quota_limit")
        quota_window = policy_dict.get("quota_window_seconds")
        if quota_limit and quota_window:
            quota_config = QuotaConfig(limit=quota_limit, window_seconds=max(1, quota_window))

        snapshot: Dict[str, Any] = {
            "policy_source": policy_source,
            "policy_id": policy_dict.get("id"),
            "tenant": tenant,
            "requested": {
                "lane": requested_lane,
                "queue": requested_queue,
                "priority": requested_priority,
                "estimated_runtime_ms": estimated_runtime_ms,
                "lane_reason": lane_reason,
            },
            "resolved": {
                "lane": resolved_lane,
                "queue": resolved_queue,
                "priority": normalized_priority,
            },
            "allowed_queues": sorted(allowed_queues),
            "max_priority": max_priority,
            "max_runtime_ms": max_runtime_ms,
            "violations": violations,
            "hard_failures": hard_failures,
            "quota_limit": quota_config.limit,
            "quota_window_seconds": quota_config.window_seconds,
        }

        allowed = not hard_failures
        denial_reason = hard_failures[0] if hard_failures else None
        if allowed:
            span.set_attribute("job.policy_queue", resolved_queue)
            span.set_attribute("job.policy_lane", resolved_lane)
            span.set_attribute("job.policy_priority", normalized_priority)
            span.set_attribute("job.policy_enforced", policy_enforced)
        else:
            span.record_exception(RuntimeError(f"policy_denied:{denial_reason}"))
            span.set_attribute("job.policy_denied", True)

        logger.info(
            "policy_decision",
            extra={
                "tenant": tenant,
                "allowed": allowed,
                "queue": resolved_queue,
                "lane": resolved_lane,
                "priority": normalized_priority,
                "violations": violations,
                "hard_failures": hard_failures,
            },
        )

        return PolicyDecision(
            tenant=tenant,
            allowed=allowed,
            queue_name=resolved_queue,
            task_type=resolved_lane,
            normalized_priority=normalized_priority,
            requested_priority=requested_priority,
            estimated_runtime_ms=estimated_runtime_ms,
            violations=violations,
            snapshot=snapshot,
            policy_enforced=policy_enforced,
            quota_config=quota_config,
            denial_reason=denial_reason,
        )


def _queue_map(settings: GatewaySettings) -> Dict[str, str]:
    return {
        "standard": settings.job.queue_name,
        "heavy": settings.job.heavy_queue_name,
        "gpu": settings.job.gpu_queue_name,
    }


def _estimate_runtime(submission: JobSubmissionRequest) -> Optional[int]:
    expression = submission.input_expression or ""
    base = len(expression) * 8
    context_weight = sum(len(str(value)) for value in submission.context.values()) * 4
    priority_weight = max(submission.priority, 0) * 50
    estimate = base + context_weight + priority_weight + 250
    if submission.requires_gpu:
        estimate *= 2
    return int(min(max(estimate, 250), 180_000))


def _classify_lane(
    submission: JobSubmissionRequest, settings: GatewaySettings
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if submission.task_type:
        lane = submission.task_type.lower()
        if lane in {"standard", "heavy", "gpu"}:
            reasons.append("task_type_hint")
            return lane, reasons
        reasons.append("invalid_task_type")

    gpu_tags = {tag.lower() for tag in settings.job.gpu_tags}
    heavy_tags = {tag.lower() for tag in settings.job.heavy_tags}
    submission_tags = {tag.lower() for tag in submission.tags}

    if submission.requires_gpu or submission_tags & gpu_tags:
        reasons.append("gpu_hint")
        return "gpu", reasons

    context = {str(key).lower(): value for key, value in submission.context.items()}
    if any(str(value).lower() in {"gpu", "cuda", "accelerator"} for value in context.values()):
        reasons.append("gpu_context_hint")
        return "gpu", reasons

    if submission_tags & heavy_tags:
        reasons.append("heavy_tag")
        return "heavy", reasons

    if _looks_heavy(submission.input_expression, settings.job.heavy_expression_keywords):
        reasons.append("heavy_expression")
        return "heavy", reasons

    if len(submission.input_expression) >= 2 * max(1, settings.job.default_max_runtime_ms // 500):
        reasons.append("heavy_length")
        return "heavy", reasons

    reasons.append("standard_default")
    return "standard", reasons


def _looks_heavy(expression: str, keywords: Iterable[str]) -> bool:
    lowered = expression.lower()
    return any(keyword in lowered for keyword in keywords)


def _select_fallback_lane(
    allowed_queues: set[str],
    queue_map: Dict[str, str],
    *,
    prefer_gpu: bool,
) -> Optional[str]:
    ordered = ["standard", "heavy", "gpu"]
    if prefer_gpu:
        ordered = ["gpu", "heavy", "standard"]
    for lane in ordered:
        if queue_map[lane] in allowed_queues:
            return lane
    return None


async def _load_policy(
    session: AsyncSession,
    redis: Redis,
    tenant: str,
    settings: GatewaySettings,
    queue_map: Dict[str, str],
) -> tuple[Dict[str, Any], str]:
    cache_key = f"{settings.job.policy_cache_namespace}:{tenant}" if settings.job.policy_cache_namespace else f"policy:{tenant}"
    cached: Optional[Dict[str, Any]] = None

    if redis is not None:
        try:
            data = await redis.get(cache_key)
        except Exception:  # noqa: BLE001 - cache failures should not block requests
            data = None
        if data:
            try:
                cached = json.loads(data)
            except (TypeError, json.JSONDecodeError):
                cached = None

    if cached is not None:
        return cached, "cache"

    stmt = select(TenantPolicy).where(TenantPolicy.tenant == tenant)
    result = await session.execute(stmt)
    record = result.scalars().first()
    if record is not None:
        policy_dict = _policy_record_to_dict(record, queue_map)
        source = "database"
    else:
        policy_dict = _default_policy(queue_map, settings)
        source = "default"

    if redis is not None:
        try:
            await redis.set(
                cache_key,
                json.dumps(policy_dict),
                ex=max(settings.job.policy_cache_ttl_seconds, 30),
            )
        except Exception:  # noqa: BLE001 - cache failures should not block requests
            pass

    return policy_dict, source


def _policy_record_to_dict(record: TenantPolicy, queue_map: Dict[str, str]) -> Dict[str, Any]:
    allowed = list(record.allowed_queues) if record.allowed_queues else list(queue_map.values())
    return {
        "id": record.id,
        "tenant": record.tenant,
        "max_priority": record.max_priority,
        "allowed_queues": allowed,
        "max_runtime_ms": record.max_runtime_ms,
        "banned_patterns": list(record.banned_patterns or []),
        "allow_heavy": record.allow_heavy,
        "allow_gpu": record.allow_gpu,
        "quota_limit": record.quota_limit,
        "quota_window_seconds": record.quota_window_seconds,
    }


def _default_policy(queue_map: Dict[str, str], settings: GatewaySettings) -> Dict[str, Any]:
    return {
        "id": None,
        "tenant": "default",
        "max_priority": settings.job.priority_levels - 1,
        "allowed_queues": list(queue_map.values()),
        "max_runtime_ms": settings.job.default_max_runtime_ms,
        "banned_patterns": [],
        "allow_heavy": True,
        "allow_gpu": False,
        "quota_limit": settings.quota.limit,
        "quota_window_seconds": settings.quota.window_seconds,
    }

