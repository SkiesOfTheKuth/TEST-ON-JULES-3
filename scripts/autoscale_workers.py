#!/usr/bin/env python3
"""CLI helper for autoscaling Celery workers based on queue pressure."""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, Optional

from services.gateway.app.autoscale import AutoscaleObservation, evaluate_autoscale
from services.gateway.app.config import get_settings
from services.gateway.app.task_queue import celery_app


def _build_observation(args: argparse.Namespace) -> AutoscaleObservation:
    return AutoscaleObservation(
        queue_depth=args.queue_depth,
        active_workers=args.active_workers,
        p95_wait_seconds=args.p95_wait,
        worker_cpu_percent=args.worker_cpu,
        last_scale_timestamp=args.last_scale_timestamp,
    )


def _load_observation_from_stdin() -> Dict[str, Any]:
    try:
        raw = sys.stdin.read().strip()
    except Exception:  # pragma: no cover - defensive
        return {}
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:  # pragma: no cover - validated in tests
        raise SystemExit(f"Invalid JSON payload on stdin: {exc}")


def _apply_scale(delta: int, drain_timeout: int, queue: str) -> None:
    if delta == 0:
        return
    if delta > 0:
        celery_app.control.pool_grow(delta)
        return

    # Scale down: drain the queue before shrinking the pool.
    celery_app.control.cancel_consumer(queue, reply=True)
    time.sleep(max(drain_timeout, 1))
    celery_app.control.pool_shrink(abs(delta))
    celery_app.control.add_consumer(queue, reply=True)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue-depth", type=int, required=False, default=0,
                        help="Current Redis queue depth for the worker queue.")
    parser.add_argument("--active-workers", type=int, required=False, default=1,
                        help="Number of worker replicas currently processing jobs.")
    parser.add_argument("--p95-wait", type=float, required=False, default=None,
                        help="Latest p95 queue wait time in seconds (optional).")
    parser.add_argument("--worker-cpu", type=float, required=False, default=None,
                        help="Average worker CPU usage percentage (optional).")
    parser.add_argument("--last-scale-timestamp", type=float, required=False, default=None,
                        help="Unix monotonic timestamp describing the previous scale event (optional).")
    parser.add_argument("--apply", action="store_true",
                        help="Invoke Celery control commands to enact the decision.")
    parser.add_argument("--stdin", action="store_true",
                        help="Read observation JSON from stdin instead of CLI flags.")
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    settings = get_settings()

    if args.stdin:
        payload = _load_observation_from_stdin()
        mapping = {
            "queue_depth": int,
            "active_workers": int,
            "p95_wait": float,
            "worker_cpu": float,
            "last_scale_timestamp": float,
        }
        for field, caster in mapping.items():
            if field in payload and payload[field] is not None:
                try:
                    value = caster(payload[field])
                except (TypeError, ValueError) as exc:
                    raise SystemExit(f"Invalid value for {field}: {payload[field]!r} ({exc})")
                setattr(args, field, value)

    observation = _build_observation(args)
    decision = evaluate_autoscale(observation, settings.autoscale)

    result = {
        "queue": settings.job.queue_name,
        "observation": {
            "queue_depth": observation.queue_depth,
            "active_workers": observation.active_workers,
            "p95_wait_seconds": observation.p95_wait_seconds,
            "worker_cpu_percent": observation.worker_cpu_percent,
            "last_scale_timestamp": observation.last_scale_timestamp,
        },
        "decision": {
            "desired_workers": decision.desired_workers,
            "action": decision.action,
            "reason": decision.reason,
            "cooldown_applied": decision.cooldown_applied,
            "next_allowed_scale_ts": decision.next_allowed_scale_ts,
        },
    }

    print(json.dumps(result, indent=2, sort_keys=True))

    if args.apply and decision.action in {"scale_up", "scale_down"}:
        delta = decision.desired_workers - observation.active_workers
        if delta != 0:
            _apply_scale(delta, settings.autoscale.drain_timeout_seconds, settings.job.queue_name)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via CLI
    raise SystemExit(main())
