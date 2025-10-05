"""Locust load test hitting the asynchronous job submission APIs."""

from __future__ import annotations

from collections import deque
import time

from locust import HttpUser, between, events, task


def _extract_metric_value(
    metrics_text: str,
    metric_name: str,
    label_filter: dict[str, str] | str | None = None,
) -> float | None:
    for line in metrics_text.splitlines():
        if not line or line.startswith("#"):
            continue
        if not line.startswith(metric_name):
            continue
        if label_filter:
            if isinstance(label_filter, dict):
                if any(f'{key}="{value}"' not in line for key, value in label_filter.items()):
                    continue
            elif label_filter not in line:
                continue
        try:
            return float(line.rsplit(" ", 1)[-1])
        except ValueError:
            continue
    return None


def _extract_histogram_average(
    metrics_text: str,
    metric_name: str,
    label_filter: dict[str, str] | str | None = None,
) -> float | None:
    total = _extract_metric_value(metrics_text, f"{metric_name}_sum", label_filter)
    count = _extract_metric_value(metrics_text, f"{metric_name}_count", label_filter)
    if total is None or count is None or count == 0:
        return None
    return (total / count) * 1000.0


class JobUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.api_key = self.environment.parsed_options.api_key
        self.recent_jobs: deque[str] = deque(maxlen=100)
        self._next_metrics_sample = 0.0

    @task(3)
    def submit_job(self):
        payload = {
            "input_expression": "(21 + 21) * 2",
            "context": {"x": 3},
            "priority": 1,
            "tags": ["load-test"],
        }
        headers = {"X-Api-Key": self.api_key}
        with self.client.post("/jobs", json=payload, headers=headers, catch_response=True) as response:
            if response.status_code not in (202, 200):
                response.failure(f"Unexpected status {response.status_code}: {response.text}")
                return
            try:
                job_id = response.json()["id"]
            except Exception as exc:  # noqa: BLE001
                response.failure(f"Failed to parse job id: {exc}")
                return
            self.recent_jobs.append(job_id)

    @task
    def poll_recent_job(self):
        if not self.recent_jobs:
            return
        job_id = self.recent_jobs[0]
        headers = {"X-Api-Key": self.api_key}
        self.client.get(f"/jobs/{job_id}", headers=headers, name="/jobs/{id}")

    @task
    def sample_metrics(self):
        now = time.time()
        if now < self._next_metrics_sample:
            return
        self._next_metrics_sample = now + 5.0

        with self.client.get("/metrics", name="/metrics (sample)", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"Metrics scrape failed: {response.status_code}")
                return
            metrics_text = response.text

        queue_depth = _extract_metric_value(
            metrics_text,
            "calculator_gateway_job_queue_depth",
            {"queue": "calculator-jobs"},
        )
        if queue_depth is not None:
            events.request_success.fire(
                request_type="GAUGE",
                name="queue_depth",
                response_time=queue_depth,
                response_length=0,
            )

        runtime_avg_ms = _extract_histogram_average(
            metrics_text,
            "calculator_gateway_job_task_runtime_seconds",
            {"queue": "calculator-jobs", "status": "succeeded"},
        )
        if runtime_avg_ms is not None:
            events.request_success.fire(
                request_type="GAUGE",
                name="worker_runtime_ms",
                response_time=runtime_avg_ms,
                response_length=0,
            )


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--api-key", required=True, help="Gateway API key for authentication")


@events.test_start.add_listener
def _validate(environment, **kwargs):
    if not getattr(environment.parsed_options, "api_key", None):
        raise RuntimeError("--api-key is required to run the load test")

