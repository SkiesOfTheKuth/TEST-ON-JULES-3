# Release Notes

## Unreleased

### Observability

- Added reusable helpers to expose Prometheus `/metrics` endpoints across gateway and worker processes, ensuring idempotent registration backed by the shared registry.
- Wired Celery worker signal hooks for tracing spans, queue wait histograms, and failure counters; provided a lightweight FastAPI metrics app for workers.
- Extended tests covering Prometheus exposure, queue instrumentation, and Celery signal lifecycles to guard the observability baseline.
- NEW: `install_prometheus_endpoint` for any ASGI app; idempotent, shared registry.
- Gateway: `/metrics` via the shared installer; enqueue header `x-enqueued-at-ms` for queue-wait tracing.
- Worker: Celery signal instrumentation with bounded-cardinality labels and a standalone FastAPI metrics app.

### Tracing

- Added end-to-end OpenTelemetry spans for enqueue, poll, WebSocket, and worker execution phases with bounded-cardinality attributes (`job_id_short`, `queue`, `task`).
- Propagated enqueue timestamps via `x-enqueued-at-ms` headers to compute `queue_wait_ms` and `worker_process_ms` inside worker spans for precise queue-to-execution correlation.
- Emitted structured retry/failure events on execution spans alongside child spans for deserialize/compute/persist/publish lifecycles, verified with an in-memory exporter test.

#### Tracing correlation & guards

- Injected and extracted W3C Trace Context headers to guarantee enqueue→execute parentage while linking downstream WebSocket spans without introducing high-cardinality labels.
- Clamped negative or missing `queue_wait_ms` values (clock skew) and logged once to avoid noisy metrics while keeping `worker_process_ms` bounded.
- Hardened span attributes to exclude full job identifiers or tenant data, preserving `job_id_short` only and capturing retry/failure events with structured error payloads.
- Enforced exact span names with a single worker execute span per task to prevent double instrumentation and metric drift.
- Documented guardrails for missing enqueue headers (attribute omitted) and negative queue waits (clamped to zero).
- Linked WebSocket spans back to enqueue contexts via `SpanLink` while keeping attributes PII-free.
- Added regression tests enforcing correlation and guardrails (parent/child linkage, queue wait omissions/clamps, WebSocket links, and single execute spans).

##### Final regression locks

- Added targeted tests to ensure missing enqueue headers omit `queue_wait_ms`, future-dated headers clamp to `0`, and nested instrumentation paths still surface a single `jobs.execute` span.
- Verified metrics guards that `jobs_in_progress` increments/decrements exactly once per task, runtime histograms record a single observation, and success paths leave failure counters unchanged.
- Final WS & metrics locks: WebSocket spans now assert a single enqueue link with bounded attributes, histogram/gauge accounting is explicitly scraped, and a Prometheus installer sanity test guards against duplicate collectors.

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
