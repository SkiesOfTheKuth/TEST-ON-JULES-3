"""Locust load test hitting the asynchronous job submission APIs."""

from collections import deque

from locust import HttpUser, between, events, task


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

