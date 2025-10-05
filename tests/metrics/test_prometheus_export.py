from prometheus_client import REGISTRY, generate_latest

from src.observability.metrics import get_job_metrics


def test_metric_collectors_registered() -> None:
    # Ensure metrics are initialised
    get_job_metrics(None)

    body = generate_latest(REGISTRY).decode("utf-8")
    for expected in (
        "jobs_enqueued_total",
        "jobs_failed",
        "jobs_in_progress",
        "queue_depth",
        "celery_task_runtime_seconds",
        "job_wait_time_seconds",
        "ws_clients",
        "ws_send_errors_total",
    ):
        assert expected in body
