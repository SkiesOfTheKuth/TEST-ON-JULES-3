from __future__ import annotations

import time

from celery import Celery

from src.worker.instrumentation import get_worker_metrics, setup_worker_signals, signals


class _TaskRequest:
    def __init__(self, task_id: str, queue: str) -> None:
        self.id = task_id
        self.headers = {"x-enqueued-at-ms": str(int(time.time() * 1000) - 250)}
        self.delivery_info = {"routing_key": queue}


class _Task:
    def __init__(self, task_id: str, queue: str, name: str = "worker.task") -> None:
        self.name = name
        self.queue = queue
        self.request = _TaskRequest(task_id, queue)


def _get_metric_value(metric, sample_name: str, **labels) -> float:
    for collector in metric.collect():
        for sample in collector.samples:
            if sample.name.endswith(sample_name) and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return 0.0


def test_worker_signal_lifecycle_updates_metrics() -> None:
    namespace = "worker_signal"
    metrics = get_worker_metrics(namespace=namespace)
    app = Celery("test-worker")
    setup_worker_signals(app, namespace=namespace)

    task = _Task("job-1", "calculator", "worker.task")

    signals.task_prerun.send(sender=app, task_id=task.request.id, task=task)
    assert _get_metric_value(
        metrics.jobs_in_progress,
        "_jobs_in_progress",
        queue="calculator",
        task="worker.task",
    ) == 1.0

    signals.task_postrun.send(
        sender=app,
        task_id=task.request.id,
        task=task,
        retval=None,
        state="SUCCESS",
    )
    assert _get_metric_value(
        metrics.jobs_in_progress,
        "_jobs_in_progress",
        queue="calculator",
        task="worker.task",
    ) == 0.0


def test_worker_signal_failure_records_counter() -> None:
    namespace = "worker_signal_failure"
    metrics = get_worker_metrics(namespace=namespace)
    app = Celery("test-worker-failure")
    setup_worker_signals(app, namespace=namespace)

    task = _Task("job-2", "calculator", "worker.task")

    signals.task_prerun.send(sender=app, task_id=task.request.id, task=task)
    signals.task_failure.send(
        sender=app,
        task_id=task.request.id,
        exception=RuntimeError("boom"),
        traceback=None,
        einfo=None,
        task=task,
    )
    signals.task_postrun.send(
        sender=app,
        task_id=task.request.id,
        task=task,
        retval=None,
        state="FAILURE",
    )

    assert _get_metric_value(
        metrics.jobs_failed,
        "_jobs_failed",
        queue="calculator",
        task="worker.task",
    ) == 1.0
