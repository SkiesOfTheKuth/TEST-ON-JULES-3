from __future__ import annotations

import time

from celery import Celery

from src.worker.instrumentation import get_worker_metrics, setup_worker_signals, signals


class _TaskRequest:
    def __init__(self, task_id: str, queue: str) -> None:
        self.id = task_id
        self.headers = {"x-enqueued-at-ms": str(int(time.time() * 1000) - 250)}
        self.delivery_info = {"routing_key": queue}
        self.retries = 0


class _Task:
    def __init__(self, task_id: str, queue: str, name: str = "worker.task") -> None:
        self.name = name
        self.queue = queue
        self.request = _TaskRequest(task_id, queue)


def _metric_value(metric, **labels) -> float:
    for collector in metric.collect():
        for sample in collector.samples:
            if all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return 0.0


def test_worker_signal_lifecycle_updates_gauge_and_histogram() -> None:
    namespace = "worker_signal_success"
    metrics = get_worker_metrics(namespace=namespace)
    app = Celery("worker-signal-success")
    setup_worker_signals(app, namespace=namespace)

    task = _Task("job-1", "calculator")

    signals.task_prerun.send(sender=app, task_id=task.request.id, task=task)
    assert _metric_value(metrics.jobs_in_progress, queue="calculator", task="worker.task") == 1.0

    signals.task_postrun.send(
        sender=app,
        task_id=task.request.id,
        task=task,
        retval=None,
        state="SUCCESS",
    )

    assert _metric_value(metrics.jobs_in_progress, queue="calculator", task="worker.task") == 0.0
    assert _metric_value(metrics.celery_task_runtime_seconds, task="worker.task") > 0.0


def test_worker_signal_failure_increments_failure_counter() -> None:
    namespace = "worker_signal_failure_metrics"
    metrics = get_worker_metrics(namespace=namespace)
    app = Celery("worker-signal-failure")
    setup_worker_signals(app, namespace=namespace)

    task = _Task("job-2", "calculator")

    signals.task_prerun.send(sender=app, task_id=task.request.id, task=task)
    signals.task_failure.send(
        sender=app,
        task_id=task.request.id,
        exception=RuntimeError("boom"),
        traceback=None,
        einfo=None,
        task=task,
    )

    assert _metric_value(metrics.jobs_in_progress, queue="calculator", task="worker.task") == 0.0
    assert _metric_value(metrics.jobs_failed, queue="calculator", task="worker.task") == 1.0

    signals.task_postrun.send(
        sender=app,
        task_id=task.request.id,
        task=task,
        retval=None,
        state="FAILURE",
    )

    assert _metric_value(metrics.celery_task_runtime_seconds, task="worker.task") > 0.0


def test_worker_signal_retry_resets_in_progress_gauge() -> None:
    namespace = "worker_signal_retry"
    metrics = get_worker_metrics(namespace=namespace)
    app = Celery("worker-signal-retry")
    setup_worker_signals(app, namespace=namespace)

    task = _Task("job-3", "calculator")

    signals.task_prerun.send(sender=app, task_id=task.request.id, task=task)
    assert _metric_value(metrics.jobs_in_progress, queue="calculator", task="worker.task") == 1.0

    signals.task_retry.send(
        sender=app,
        request=task.request,
        reason=RuntimeError("temporary"),
        einfo=None,
    )

    assert _metric_value(metrics.jobs_in_progress, queue="calculator", task="worker.task") == 0.0

    signals.task_prerun.send(sender=app, task_id=task.request.id, task=task)
    assert _metric_value(metrics.jobs_in_progress, queue="calculator", task="worker.task") == 1.0
