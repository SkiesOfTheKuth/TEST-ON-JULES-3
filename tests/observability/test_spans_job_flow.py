import time

from src.gateway.instrumentation import start_enqueue_span
from src.observability.metrics import get_job_metrics
from src.worker.instrumentation import worker_task_span


def test_enqueue_and_worker_spans_include_expected_attributes() -> None:
    job_id = "abcd1234efgh5678"
    queue = "calculator"
    task = "gateway.execute_job"

    with start_enqueue_span(job_id, queue, task) as enqueue_span:
        pass

    metrics = get_job_metrics(None)
    headers = {"x-enqueued-at-ms": str(int((time.time() - 0.05) * 1000))}

    with worker_task_span(job_id, queue, task, headers, metrics) as worker_span:
        time.sleep(0.01)

    assert enqueue_span.attributes["job_id"] == job_id.replace("-", "")[:8]
    enqueue_events = {name: attrs for name, attrs in enqueue_span.events}
    assert enqueue_events["job.id"]["job_id"] == job_id

    assert worker_span.attributes["queue"] == queue
    assert worker_span.attributes["task"] == task
    assert worker_span.attributes["outcome"] == "success"
    assert "queue_wait_ms" in worker_span.attributes
    assert worker_span.attributes["worker_process_ms"] >= 0.0
    worker_events = {name: attrs for name, attrs in worker_span.events}
    assert worker_events["job.id"]["job_id"] == job_id
