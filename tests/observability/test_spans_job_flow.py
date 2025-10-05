import time

from src.gateway.instrumentation import start_enqueue_span
from src.observability.metrics import get_job_metrics
from src.worker.instrumentation import worker_task_span


def _counter_value(metric, **labels) -> float:
    child = metric.labels(**labels)
    child.inc(0)
    sample = next(
        sample
        for collector in metric.collect()
        for sample in collector.samples
        if all(sample.labels.get(k) == v for k, v in labels.items())
    )
    return sample.value


def test_enqueue_and_worker_spans_include_expected_attributes() -> None:
    job_id = "abcd1234efgh5678"
    queue = "calculator"
    task = "gateway.execute_job"

    with start_enqueue_span(job_id, queue, task) as enqueue_span:
        pass

    metrics = get_job_metrics(None)
    headers = {"x-enqueued-at-ms": str(int((time.time() - 0.05) * 1000))}

    metrics.jobs_in_progress.labels(queue=queue, task=task).inc()
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


def test_worker_span_failed_outcome_increments_metrics() -> None:
    job_id = "ffcc0011aaee7788"
    queue = "calculator"
    task = "gateway.execute_job"
    metrics = get_job_metrics(None)
    headers = {"x-enqueued-at-ms": str(int(time.time() * 1000))}

    before = _counter_value(metrics.jobs_failed, queue=queue, task=task)
    metrics.jobs_in_progress.labels(queue=queue, task=task).inc()
    with worker_task_span(job_id, queue, task, headers, metrics) as span:
        span.set_attribute("outcome", "failed")

    after = _counter_value(metrics.jobs_failed, queue=queue, task=task)
    assert after == before + 1
