# Operations Guide

## Phase 2 Stack Overview
- **Gateway** (`services/gateway`): FastAPI service exposing synchronous `/calculate` and asynchronous `/jobs` APIs, policy engine, Celery orchestration, and WebSocket notifications.
- **Safe Evaluator** (`services/safe_evaluator`): gRPC sandbox that validates expressions, enforces complexity budgets, and executes computations in an isolated runtime.
- **Workers**: Three Celery worker profiles launched via Compose—`worker-standard`, `worker-priority` (heavy math lane), and `worker-gpu` (GPU lane). All publish status updates back to Redis and Prometheus.
- **Backing services**: Postgres (API keys, job ledger, policy records), Redis (broker, cache, policy store), and the observability suite (Tempo, Prometheus, Loki, Grafana).

## Bootstrapping
1. Install Docker Desktop (or Docker Engine), Python 3.11+, and `make`.
2. Copy `.env.development` to `.env` for local overrides when needed.
3. Run `make bootstrap` from the repository root to install Poetry-managed dependencies for the gateway and safe evaluator services.
4. Apply database migrations:
   ```bash
   poetry -C services/gateway run alembic upgrade head
   ```
5. Seed an API key for local usage (repeatable and idempotent):
   ```bash
   poetry -C services/gateway run python -m app.scripts.seed_api_key --api-key local-dev-key --owner "Local Dev" --scopes calculate --force
   ```

## Running the Phase 2 Stack
- Start everything (Postgres, Redis, gateway, safe evaluator, workers, observability):
  ```bash
  make compose-phase2-up
  ```
  Services come up on:
  - Gateway API: `http://localhost:8080`
  - Grafana: `http://localhost:3000` (`admin` / `grafana`)
  - Redis: `localhost:6379`
  - Postgres: `localhost:5432` (`calculator` / `calculator`)

- Tear everything down, including volumes:
  ```bash
  make compose-phase2-down
  ```

- Targeted stack for tests (CI parity):
  ```bash
  make integration
  ```
  This brings up database, broker, evaluator, all three workers, and observability, waits for readiness, runs migrations, executes the integration test suite, and then tears everything down.

## API Key and Policy Management
- **Seeding keys:** use the `seed_api_key` helper as shown above. Keys are hashed in Postgres and cached in Redis.
- **Rotating keys:** reseed with `--force`, update consumers, then deactivate old keys by setting `active = false` in the `api_keys` table.
- **Tenant policies:** stored in `tenant_policies`. Key columns:
  - `allowed_queues`: queue names permitted for the tenant (includes GPU lane when enabled).
  - `allow_heavy` / `allow_gpu`: feature gates for heavy math and GPU routes.
  - `banned_patterns`: case-insensitive regex list to deny unsafe expressions.
  - `quota_limit`, `quota_window_seconds`: overrides for per-tenant quotas.
  Edits should be followed by flushing the cache entry: `redis-cli DEL policy:<tenant>` (or the namespace configured via `GATEWAY_JOB__POLICY_CACHE_NAMESPACE`).

## Queue Operations
- Inspect workers and queues:
  ```bash
  poetry -C services/gateway run celery -A app.task_queue inspect active
  poetry -C services/gateway run celery -A app.task_queue inspect stats
  poetry -C services/gateway run celery -A app.task_queue inspect active_queues
  ```
- Drain or purge cautiously:
  ```bash
  poetry -C services/gateway run celery -A app.task_queue control cancel_consumer calculator-jobs -d worker@<host>
  poetry -C services/gateway run celery -A app.task_queue purge
  ```
- Poll queue depth metrics without leaving the CLI:
  ```bash
  curl -s http://localhost:8080/metrics | grep calculator_gateway_job_queue_depth
  ```

## Autoscaling Guidance
- The decision helper lives in `services/gateway/app/autoscale.py`. It considers queue depth, p95 wait time, CPU, and cooldown windows.
- Use the CLI wrapper to evaluate or apply scale operations:
  ```bash
  python scripts/autoscale_workers.py --queue-depth 120 --active-workers 3 --p95-wait 8 --worker-cpu 87
  ```
  Add `--apply` to invoke Celery control commands (grow/shrink pool, drain queues) once telemetry meets thresholds. Provide `--stdin` to ingest Prometheus snapshots or JSON payloads from automation.
- Default thresholds (configurable via `AutoscaleSettings`):
  - Scale up when queue depth >= 75% of `job.max_queue_size`, p95 wait > 5s, or worker CPU > 85%.
  - Scale down when queue depth <= 15% and both latency and CPU fall below half the target values.
  - Cooldown between scale decisions: 180 seconds; drain timeout before shrink: 30 seconds.

## Observability
- Gateway metrics: `http://localhost:8080/metrics` exposes request counters, job queue gauges, runtime histograms, policy rejections, worker failure counters, and per-queue CPU utilisation (`calculator_gateway_worker_cpu_percent`).
- Grafana dashboards (`observability/grafana/dashboards`):
  - **Gateway Overview:** request rate, latency, async job throughput, queue depth, success/failure ratios, and policy decisions.
  - **Phase 2 Queue Lanes:** per-lane queue depth, enqueue/throughput, autoscale events, and worker utilisation gauges.
  - **Worker Health:** Celery worker heartbeats, queue wait histograms, failure reasons.
- Tempo captures traces with queue wait attributes and policy decisions. Loki aggregates structured JSON logs (request IDs, trace IDs, tenant, queue decisions).

## Runbooks

### Celery Worker Lifecycle
1. **Deploy new workers**: build and publish the image, then scale out (`docker compose up -d worker` or `kubectl rollout restart deployment/gateway-worker`). Monitor `calculator_gateway_worker_up{worker}` for the new hostname and ensure `calculator_gateway_worker_utilization` stays below the configured concurrency target while warming.
2. **Drain old replicas**: once the new workers show heartbeats, ask legacy workers to finish in-flight tasks: `celery -A services.gateway.app.task_queue control cancel_consumer <queue> -d worker@old-host`. Wait for `calculator_gateway_jobs_in_progress` for that worker to drop to zero before stopping the pod/container.
3. **Rollback**: if error rates spike, redeploy the previous image and re-enable consumers with `celery -A services.gateway.app.task_queue control add_consumer <queue> -d worker@old-host`. Because jobs persist in Postgres/Redis, drained queues resume automatically. Compare `calculator_gateway_policy_violations_total` before/after rollout to spot regressions.

### Redis Outage Recovery
1. Confirm the broker endpoint (`redis-cli -u $GATEWAY_REDIS__URL ping`). If unreachable, fail over to the replica or restart the managed instance.
2. Inspect queued keys before flushing: `redis-cli -u $GATEWAY_REDIS__URL -n 0 keys 'celery*'`. Prefer targeted deletes and only purge (`celery -A services.gateway.app.task_queue purge`) when corruption is confirmed.
3. Restart workers after broker recovery to renew connections and reload caches.
4. Submit a synthetic job (`make smoke-job` or POST `/jobs`) and watch `calculator_gateway_job_queue_depth` plus the WebSocket channel to ensure events propagate.
5. Use Grafana's **Phase 2 Queue Lanes** panel to verify depth drains to baseline and `calculator_gateway_autoscale_events_total{direction="scale_down"}` fires once backlog clears.

### Policy Engine Tuning
1. Review recent violations in Grafana (`calculator_gateway_policy_violations_total`) and Loki (`policy_outcome` field). Identify tenants with repeated `violation` decisions.
2. Fetch the current policy from Postgres (`SELECT * FROM tenant_policies WHERE tenant = '<id>';`) or update via admin tooling. Adjust `allowed_queues`, `max_runtime_ms`, `max_priority`, etc.
3. Clear the cache entry so changes take effect: `redis-cli -u $GATEWAY_REDIS__URL DEL policy:<tenant>` (namespace honours `job.policy_cache_namespace`).
4. Re-run the offending workload and confirm `calculator_gateway_policy_decisions_total{decision="allow"}` increments while violations stop climbing. Keep traces handy to ensure rerouted queues (`job.queue_name`) align with expectations.

### Dashboard Guide
- **Gateway Overview** (`http://localhost:3000/d/Gateway/gateway-overview` – credentials `admin`/`grafana`): track inbound request health. Red thresholds on request rate or p95 latency signal API-side stress.
- **Phase 2 Queue Lanes** (`uid: phase2-queue`): watch per-lane depth, enqueue throughput, and `calculator_gateway_autoscale_events_total`. Use this view when tuning worker counts or investigating backlog complaints.
- **Worker Health** (`uid: worker-health`): surface `calculator_gateway_worker_up` heartbeats, queue wait histograms, and failure reasons. Correlate with Celery logs for flaky hosts.
- **Tempo traces**: search by `job.id` and inspect span attributes (`calculator.queue`, `calculator.policy_outcome`) to diagnose per-job latency.

## Integration and Load Testing
- Run the full integration suite (requires Phase 2 stack running or `make integration`):
  ```bash
  poetry -C services/gateway run pytest tests/integration -m integration
  ```
  Coverage:
  - Multi-queue routing across standard, heavy, and GPU lanes.
  - Policy enforcement (allow/deny, queue overrides, quota rejection).
  - WebSocket job lifecycle streaming.
  - Resilience (sandbox validation errors, failure metrics).
  - Autoscale decision helper sanity checks.

- Load testing (Locust) with enforced thresholds:
  ```bash
  API_KEY=<key> make load-test
  ```
  Tunable environment variables:
  - `LOCUST_MAX_P95_MS` (default `750`) – allowable p95 response time.
  - `LOCUST_MIN_RPS` (default `5`) – minimum aggregate throughput.
  - `LOCUST_MAX_FAILURE_RATIO` (default `0.05`) – acceptable failure rate.
  Failure to meet thresholds raises an exception and exits with non-zero status.

## Release Readiness Checklist
1. Ensure CI (`Phase 2 CI/CD` workflow) is green: lint, unit, integration (with real Redis/Celery), optional load tests.
2. Verify dashboards reflect new metrics; export updates into `observability/grafana/dashboards/` when changes are made.
3. Confirm policy updates, migrations, and job scripts are documented in `docs/OPERATIONS.md`, `CALCULATOR_USAGE.txt`, and relevant ADRs.
4. Update `docs/CHANGE_LOG.md` with dated entries per workstream and retain supporting PR links.
5. Run `make compose-phase2-up`, submit representative jobs (standard, heavy, gpu), observe WebSocket streams, and confirm queue depth drains under load.
6. Cut release tag only after documentation, changelog, and dashboard artifacts are merged.

## Recovery Playbooks
- **Redis outage:** verify service health, flush broker only as last resort (`redis-cli -n 0 keys 'celery*'`). Restart workers to restore connections, then submit synthetic jobs to rebuild caches.
- **Worker crash:** inspect Celery logs via `docker compose logs worker-*`. Jobs re-queue automatically; monitor `calculator_gateway_jobs_failed_total` for spikes. Scale replacement workers before draining the failed node.
- **Evaluator saturation:** traces will show `evaluator_error` or `resource_exhausted`. Scale evaluator replicas or adjust policy `max_runtime_ms`. Gateway returns HTTP 429 for rate-limited calls and 503 if queues exceed `max_queue_size`.

Keep this document aligned with every platform change. Run `scripts/ensure_changelog_updated.py` locally if unsure whether a changelog entry is required.