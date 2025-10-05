# Release Notes

## phase2-alpha.1

### Highlights

- Introduced distributed job orchestration with Celery + Redis, including queue wait and runtime telemetry across gateway and workers.
- Added WebSocket notification hardening with Redis channel validation, failure counters, and Grafana panels for ws_clients/ws_send_errors_total.
- Centralised Prometheus metric registration (`jobs_enqueued_total`, `jobs_failed`, `jobs_in_progress`, `queue_depth`, `celery_task_runtime_seconds`, `job_wait_time_seconds`) with automated CI validation.
- Delivered new runbooks for WebSocket recovery, stuck jobs, queue backlog mitigation, and Redis restoration.
- Published Grafana dashboard `calculator-phase2.json` summarising throughput, success rate, queue depth, task latency, wait-time quantiles, and WebSocket health.
- Expanded operations guide and usage docs with async job workflows, Celery command cookbook, and metrics quick checks.

### Upgrade Notes

- Deploy the new Grafana dashboard (`grafana/dashboards/calculator-phase2.json`) or enable provisioning in your Grafana instance.
- Ensure the gateway and worker images include the updated observability modules before tagging `phase2-alpha.1`.
- Update CI pipelines to use `.github/workflows/ci.yaml`, which now enforces metric exposure via the integration smoke test.
- After verification, tag the repo with `git tag phase2-alpha.1 && git push origin phase2-alpha.1`.
