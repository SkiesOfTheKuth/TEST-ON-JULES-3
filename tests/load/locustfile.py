"""Locust load test hitting the asynchronous job submission APIs."""

import logging
import os
from collections import deque

from locust import HttpUser, between, events, task

logger = logging.getLogger(__name__)

MAX_P95_MS = float(os.getenv("LOCUST_MAX_P95_MS", "750"))
MIN_RPS = float(os.getenv("LOCUST_MIN_RPS", "5"))
MAX_FAILURE_RATIO = float(os.getenv("LOCUST_MAX_FAILURE_RATIO", "0.05"))


class JobUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.api_key = self.environment.parsed_options.api_key
        self.recent_jobs: deque[str] = deque(maxlen=100)

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


@events.init_command_line_parser.add_listener
def _(parser):
    parser.add_argument("--api-key", required=True, help="Gateway API key for authentication")


@events.test_start.add_listener
def _validate(environment, **kwargs):
    if not getattr(environment.parsed_options, "api_key", None):
        raise RuntimeError("--api-key is required to run the load test")


@events.test_stop.add_listener
def _enforce_thresholds(environment, **kwargs):
    stats = environment.stats.total
    if stats.num_requests == 0:
        logger.warning("No requests executed during load test; skipping threshold checks")
        return

    p95 = stats.get_response_time_percentile(0.95)
    start = getattr(stats, "start_time", None)
    end = getattr(stats, "last_request_timestamp", None)
    duration = (end - start) if (start is not None and end is not None) else None
    if not duration or duration <= 0:
        duration = getattr(environment.runner, "run_time", None)
    if not duration or duration <= 0:
        duration = stats.avg_response_time / 1000.0 if stats.avg_response_time else 0.0
    if not duration or duration <= 0:
        duration = 1.0

    rps = getattr(stats, "total_rps", 0.0) or (stats.num_requests / duration)
    fail_ratio = stats.fail_ratio

    violations: list[str] = []
    if p95 > MAX_P95_MS:
        violations.append(f"p95 {p95:.1f}ms exceeds {MAX_P95_MS:.1f}ms")
    if rps < MIN_RPS:
        violations.append(f"throughput {rps:.2f} rps below {MIN_RPS:.2f} rps")
    if fail_ratio > MAX_FAILURE_RATIO:
        violations.append(f"fail ratio {fail_ratio:.3f} above {MAX_FAILURE_RATIO:.3f}")

    if violations:
        message = "; ".join(violations)
        logger.error("Load test thresholds violated: %s", message)
        raise RuntimeError(f"Load test thresholds violated: {message}")

    logger.info(
        "Load test thresholds satisfied (p95=%.1fms, rps=%.2f, fail_ratio=%.3f)",
        p95,
        rps,
        fail_ratio,
    )