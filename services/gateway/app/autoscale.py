"""Autoscaling evaluation utilities for Celery workers."""

from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Optional

from .config import AutoscaleSettings


@dataclass(slots=True)
class AutoscaleObservation:
    """Snapshot of workload pressure used to make autoscaling decisions."""

    queue_depth: int
    active_workers: int
    p95_wait_seconds: Optional[float] = None
    worker_cpu_percent: Optional[float] = None
    last_scale_timestamp: Optional[float] = None


@dataclass(slots=True)
class AutoscaleDecision:
    """Outcome of an autoscaling evaluation."""

    desired_workers: int
    action: str
    reason: str
    cooldown_applied: bool
    next_allowed_scale_ts: Optional[float]


_DEFENSIVE_REASON = "within_slo"


def evaluate_autoscale(
    observation: AutoscaleObservation,
    settings: AutoscaleSettings,
    *,
    now: Optional[float] = None,
) -> AutoscaleDecision:
    """Decide whether to scale worker replicas up or down."""

    now = monotonic() if now is None else now

    decision_reason = _DEFENSIVE_REASON
    desired_workers = observation.active_workers
    action = "hold"

    # Force to the configured minimum regardless of telemetry.
    if observation.active_workers < settings.min_workers:
        desired_workers = settings.min_workers
        action = "scale_up"
        decision_reason = "below_min_workers"

    trigger_reason: Optional[str] = None
    if observation.queue_depth >= settings.scale_up_queue_threshold:
        trigger_reason = f"queue_depth>={settings.scale_up_queue_threshold}"
    elif (
        observation.p95_wait_seconds is not None
        and observation.p95_wait_seconds > settings.target_queue_wait_p95_seconds
    ):
        trigger_reason = (
            f"queue_wait>{settings.target_queue_wait_p95_seconds:.1f}s"
        )
    elif (
        observation.worker_cpu_percent is not None
        and observation.worker_cpu_percent > settings.target_cpu_percent
    ):
        trigger_reason = (
            f"worker_cpu>{settings.target_cpu_percent:.0f}%"
        )

    if trigger_reason and action != "scale_up":
        desired_workers = min(
            settings.max_workers,
            observation.active_workers + settings.scale_up_step,
        )
        if desired_workers > observation.active_workers:
            action = "scale_up"
            decision_reason = trigger_reason

    if action == "hold" and observation.active_workers > settings.min_workers:
        queue_below_threshold = (
            observation.queue_depth <= settings.scale_down_queue_threshold
        )
        wait_within_budget = (
            observation.p95_wait_seconds is None
            or observation.p95_wait_seconds
            <= settings.target_queue_wait_p95_seconds * 0.5
        )
        cpu_resting = (
            observation.worker_cpu_percent is None
            or observation.worker_cpu_percent < settings.target_cpu_percent * 0.5
        )
        if queue_below_threshold and wait_within_budget and cpu_resting:
            desired_workers = max(
                settings.min_workers,
                observation.active_workers - settings.scale_down_step,
            )
            if desired_workers < observation.active_workers:
                action = "scale_down"
                decision_reason = "queue_depth"

    if action != "hold" and observation.last_scale_timestamp is not None:
        elapsed = now - observation.last_scale_timestamp
        if elapsed < settings.cooldown_seconds:
            remaining = int(settings.cooldown_seconds - elapsed)
            return AutoscaleDecision(
                desired_workers=observation.active_workers,
                action="hold",
                reason=f"cooldown_active({remaining}s)",
                cooldown_applied=True,
                next_allowed_scale_ts=
                    observation.last_scale_timestamp + settings.cooldown_seconds,
            )

    next_allowed = (
        now + settings.cooldown_seconds if action != "hold"
        else observation.last_scale_timestamp
    )
    return AutoscaleDecision(
        desired_workers=desired_workers,
        action=action,
        reason=decision_reason,
        cooldown_applied=False,
        next_allowed_scale_ts=next_allowed,
    )


__all__ = [
    "AutoscaleObservation",
    "AutoscaleDecision",
    "evaluate_autoscale",
]
