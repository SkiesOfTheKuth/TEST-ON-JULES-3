from datetime import timedelta

import pytest

from services.gateway.app.autoscale import AutoscaleDecision, AutoscaleObservation, evaluate_autoscale
from services.gateway.app.config import AutoscaleSettings


@pytest.fixture
def settings() -> AutoscaleSettings:
    return AutoscaleSettings(
        min_workers=1,
        max_workers=10,
        scale_up_step=2,
        scale_down_step=1,
        scale_up_queue_threshold=75,
        scale_down_queue_threshold=10,
        target_queue_wait_p95_seconds=5.0,
        target_cpu_percent=80.0,
        cooldown_seconds=60,
        drain_timeout_seconds=30,
    )


def test_scale_up_on_queue_depth(settings: AutoscaleSettings) -> None:
    observation = AutoscaleObservation(queue_depth=120, active_workers=3)
    decision = evaluate_autoscale(observation, settings, now=0)
    assert decision.action == "scale_up"
    assert decision.desired_workers == 5
    assert not decision.cooldown_applied


def test_scale_down_when_idle(settings: AutoscaleSettings) -> None:
    observation = AutoscaleObservation(
        queue_depth=2,
        active_workers=4,
        p95_wait_seconds=0.1,
        worker_cpu_percent=20.0,
    )
    decision = evaluate_autoscale(observation, settings, now=0)
    assert decision.action == "scale_down"
    assert decision.desired_workers == 3


def test_cooldown_blocks_chatter(settings: AutoscaleSettings) -> None:
    observation = AutoscaleObservation(
        queue_depth=90,
        active_workers=4,
        last_scale_timestamp=10.0,
    )
    decision = evaluate_autoscale(observation, settings, now=20.0)
    assert decision.action == "hold"
    assert decision.cooldown_applied
    assert decision.next_allowed_scale_ts == pytest.approx(70.0)


