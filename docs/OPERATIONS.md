# Operations Guide

## Bootstrapping

1. Install system dependencies: Docker (or Podman), Python 3.11+, and `make`.
2. Copy `.env.development` to `.env` for local overrides.
3. Run `make bootstrap` to install editable packages for both services and shared libraries.
4. Apply migrations:
   ```bash
   cd services/gateway
   alembic upgrade head
   ```

## API Key Seeding

1. Launch a Python shell within the gateway service context:
   ```bash
   python - <<'PY'
   import asyncio
   from sqlalchemy import insert
   from services.gateway.app.database import get_session
   from services.gateway.app.models import APIKey
   from services.gateway.app.security import hash_api_key

   async def main() -> None:
       async for session in get_session():
           stmt = insert(APIKey).values(
               key_hash=hash_api_key("local-dev-key"),
               owner="local-dev",
               scopes="calculate",
           )
           await session.execute(stmt)
           await session.commit()
           break

   asyncio.run(main())
   PY
   ```
2. Use the raw key (`local-dev-key`) when calling the gateway.

## Rotating Keys

1. Insert a new row with the replacement key hash and desired scopes.
2. Mark the old key as inactive (`active = false`).
3. Redis caches results per key; no restart is required.

## Observability Stack

The Compose environment now ships a full observability suite wired end-to-end:

* **Tracing:** Both the FastAPI gateway and gRPC evaluator emit OpenTelemetry traces with W3C context propagation (`traceparent` header → gRPC metadata). Spans are exported to Tempo via OTLP/HTTP (`http://tempo:4318/v1/traces`).
* **Metrics:**
  - Gateway exposes Prometheus metrics on `:8080/metrics`, including request counters (`requests_total`), latency histograms, and a rolling gauge of rate-limit rejections per reason.
  - Phase 2 introduces asynchronous job series with shared names across gateway and workers: counters (`jobs_enqueued_total`, `jobs_failed{queue,task}`), gauges (`jobs_in_progress{queue,task}`, `queue_depth{queue}`, `ws_clients{endpoint}`), histograms (`celery_task_runtime_seconds{task}`, `job_wait_time_seconds{queue}`), and error counters (`ws_send_errors_total{endpoint}`, `job_notifications_failed_total`).
  - The evaluator publishes metrics on `:9464` covering execution duration histograms, in-flight queue depth, sandbox restart counters, and default process resource gauges.
  - Prometheus scrapes both endpoints (`observability/prometheus.yml`).
* **Logging:** Structured JSON logs with `request_id`, `trace_id`, and `span_id` are shipped to Loki via a Promtail sidecar that tails Docker logs (`observability/promtail-config.yaml`).
* **Dashboards & Alerts:** Grafana is pre-provisioned with data sources, dashboards (`Gateway Overview`, `Evaluator Health`), and alert rules. Dashboards live under `observability/grafana/dashboards/`; provisioning (data sources, alert contact points, notification policies, rules) is in `observability/grafana/provisioning/`. The `Gateway Overview` board now includes async job throughput, success rate, and average wait time panels fed by the metrics above.

> Tip: `docker compose -f docker-compose.phase1.yml up --build` launches the entire stack. Grafana is reachable on `http://localhost:3000` (admin password `grafana`).

## Job Management Command Cookbook

The Celery application in `services.gateway.app.task_queue` underpins all asynchronous job orchestration. Keep the following commands close at hand:

### Celery inspection & lifecycle

```bash
celery -A services.gateway.app.task_queue inspect active
celery -A services.gateway.app.task_queue inspect reserved
celery -A services.gateway.app.task_queue inspect scheduled
celery -A services.gateway.app.task_queue inspect active_queues
celery -A services.gateway.app.task_queue purge -Q calculator --force
celery -A services.gateway.app.task_queue control revoke <task_id> --terminate --signal=SIGTERM
celery -A services.gateway.app.task_queue control add_consumer calculator --destination=worker@%h
celery -A services.gateway.app.task_queue control cancel_consumer calculator --destination=worker@%h
```

### Metrics quick checks

```bash
curl -fsS http://localhost:8080/metrics | grep jobs_enqueued_total
curl -fsS http://localhost:8080/metrics | grep jobs_in_progress
curl -fsS http://localhost:8080/metrics | grep queue_depth
curl -fsS http://localhost:8080/metrics | grep job_wait_time_seconds
```

### Scaling workers

```bash
# Docker Compose (local)
docker compose -f docker-compose.phase1.yml up --build -d --scale worker=4

# Kubernetes (manifests under deploy/k8s)
kubectl scale deployment calculator-worker --replicas=6
kubectl autoscale deployment calculator-worker --cpu-percent=70 --min=2 --max=10
```

Combine these commands with the runbooks in `docs/runbooks/` for repeatable incident response.

## Securing Gateway ↔ Evaluator Traffic

TLS between the gateway and evaluator is optional but fully supported. To enable:

1. Provision certificates for the evaluator service:
   * `server.crt` / `server.key` issued for the evaluator hostname (e.g., `safe-evaluator`).
   * Optional client CA bundle (PEM) if you plan to enforce mutual TLS.
2. Mount the certificate material into the evaluator container and set:
   ```dotenv
   EVALUATOR_USE_TLS=true
   EVALUATOR_SERVER_CERT_PATH=/certs/server.crt
   EVALUATOR_SERVER_KEY_PATH=/certs/server.key
   # Optional – supply the CA bundle to require client certificates
   EVALUATOR_CLIENT_CA_PATH=/certs/ca.pem
   ```
3. Configure the gateway client to trust the evaluator certificate and, for mTLS, present its own certificate:
   ```dotenv
   GATEWAY_EVALUATOR__USE_TLS=true
   GATEWAY_EVALUATOR__ROOT_CERT_PATH=/certs/ca.pem
   GATEWAY_EVALUATOR__CLIENT_CERT_PATH=/certs/gateway.crt
   GATEWAY_EVALUATOR__CLIENT_KEY_PATH=/certs/gateway.key
   ```
4. Restart both services. The evaluator will refuse plaintext connections when TLS is enabled; ensure the gateway is updated simultaneously.

Mutual TLS is optional—leave `EVALUATOR_CLIENT_CA_PATH` unset to accept TLS without client auth.

## Testing Strategy

### Unit Tests

* **Evaluator:** Cover AST guards, timeout handling, error paths, and float precision edge cases.
* **Gateway:** Exercise authentication middleware, rate-limit logic, cache behavior, and gRPC client stub interactions via mocks.
* **Job orchestration:** Validate that `create_job` persists queued records and that Redis job cache entries are written with the expected metadata payload.

### Integration Tests

* Launch the evaluator service via a pytest fixture that manages the subprocess lifecycle.
* Exercise gateway HTTP endpoints to verify end-to-end HTTP ↔ gRPC requests and responses.
* Validate rate-limiting by simulating bursts that exceed configured quotas.
* Confirm the observability surface by asserting the metrics endpoint exposes the expected Prometheus series.
* Run the Celery task suite with `task_always_eager = True` to verify lifecycle transitions (`queued → running → succeeded/failed`) and result caching updates.

### Load Testing

* The `tests/load/locustfile.py` script drives asynchronous job submissions and polling using Locust. Launch with:
  ```bash
  poetry run locust -f tests/load/locustfile.py --host=http://localhost:8080 --api-key=<key>
  ```
* Track throughput, queue depth, and worker latency in Grafana (`Gateway Overview` → `Async Jobs`). Export the Locust CSV/JSON stats into Prometheus via the pushgateway or scrape Locust's `/stats/requests/csv` endpoint for longer runs.

### Security Tests

* Fuzz expression inputs with payloads (e.g., `__import__`, infinite loops) to ensure the evaluator rejects unsafe constructs.
* Incorporate static analysis (Bandit, Semgrep) into the CI pipeline.

### Chaos Testing (Mini)

* Terminate the evaluator mid-request and verify the gateway responds with HTTP 503 and retry guidance.
* Simulate a Redis outage to ensure the gateway degrades gracefully—disabling caching while continuing to serve requests.

## Resiliency Drills

* **Evaluator crash:** Stop the evaluator container and confirm the gateway returns 503 responses and recovers once the container restarts.
* **Redis outage:** Pause the Redis container; the gateway should continue serving requests without caching but still enforce quotas from Postgres.
* **Load tests:** Use the provided Locust plan (`tests/load/locustfile.py`) or complementary tools such as `k6` to validate throughput targets. Focus on ensuring rate limits and cache hit ratios behave as expected.

## Asynchronous Job Runbooks

### Handling Stuck Jobs

1. Confirm that the job is no longer updating by inspecting Redis and Postgres:
   ```bash
   celery -A services.gateway.app.task_queue inspect active --timeout=10
   curl -s http://localhost:8080/metrics | grep calculator_gateway_jobs_in_progress
   ```
2. Locate the job metadata (status, attempt count, worker hostname) via SQL:
   ```bash
   psql $GATEWAY_DATABASE__URL -c "SELECT id, status, started_at, error FROM jobs WHERE id = '<job-id>'"
   ```
3. If a worker is wedged, revoke the task and optionally terminate the worker process:
   ```bash
   celery -A services.gateway.app.task_queue control revoke <job-id> --terminate --signal=SIGTERM
   ```
4. Reset the job back to queued status and re-enqueue when safe:
   ```bash
   psql $GATEWAY_DATABASE__URL -c "UPDATE jobs SET status='queued', started_at=NULL, completed_at=NULL, error=NULL WHERE id='<job-id>'"
   python - <<'PY'
   from services.gateway.app.task_queue import enqueue_job

   enqueue_job("<job-id>")
   PY
   ```
5. Track recovery on Grafana (`Gateway Overview → Async Job Throughput`) and via the `calculator_gateway_job_queue_depth` gauge.

### WebSocket Notification Channel

1. Authenticate by passing `X-Api-Key` during the WebSocket handshake. The gateway reuses the REST dependency, so local overrides from tests (e.g., dependency injection) also apply.
2. On connect the gateway replays the cached payload (from Redis or Postgres) before streaming incremental updates published by workers. Expect the first frame to contain `status="queued"` along with polling links.
3. Redis pub/sub channels follow `JobSettings.notification_namespace`. If notifications stall, inspect `redis-cli pubsub channels job_events:*` to confirm messages are flowing. Then verify Celery workers are still consuming the calculator queue with `celery -A services.gateway.app.task_queue inspect active_queues --destination=worker@%h`; restart any missing workers so they re-subscribe to Redis notifications.
4. Clients should treat WebSocket disconnects as transient. Reconnect with exponential backoff and fall back to `GET /jobs/{id}` until the socket stabilizes.
5. To smoke-test end to end, run `wscat -c ws://localhost:8080/ws/jobs/<id> -H "X-Api-Key: $API_KEY"` while submitting new jobs; observe `queued → running → succeeded` frames within a few hundred milliseconds of worker transitions.

### Clearing Failed Queue

1. Quantify failures and reasons:
   ```bash
   curl -s http://localhost:8080/metrics | grep calculator_gateway_jobs_failed_total
   psql $GATEWAY_DATABASE__URL -c "SELECT id, error FROM jobs WHERE status='failed' ORDER BY completed_at DESC LIMIT 50"
   ```
2. Requeue idempotent jobs in bulk:
   ```bash
   psql $GATEWAY_DATABASE__URL -c "UPDATE jobs SET status='queued', error=NULL WHERE status='failed' AND tags @> '{"retryable"}'"
   python - <<'PY'
   from services.gateway.app.task_queue import enqueue_job

   enqueue_job("<job-id>")
   PY
   ```
3. Purge irrecoverable messages from Redis to free capacity:
   ```bash
   celery -A services.gateway.app.task_queue purge
   ```
4. Create a postmortem entry noting root cause, affected tenants, and remediation. Update Grafana annotations if required.

### Scaling Workers

1. Watch the Prometheus series `calculator_gateway_job_queue_depth` and `calculator_gateway_jobs_in_progress`.
2. Scale out when the queue depth exceeds 75% of `GATEWAY_JOB__MAX_QUEUE_SIZE` or when `jobs_in_progress` stays near concurrency for five minutes.
3. Add workers:
   ```bash
   celery -A services.gateway.app.task_queue worker --loglevel=info --queues calculator-jobs --hostname worker@%h
   ```
4. Verify heartbeats and throughput in Grafana, then update deployment manifests (Helm values, Compose replicas) for persistence.
5. Scale back down once queue depth drops below 25% of capacity for ten minutes, gracefully draining workers with `celery ... control cancel_consumer` before shutdown.

### Restoring Redis After Outage

1. Confirm Redis is reachable again (`redis-cli ping`).
2. Flush corrupt broker entries only if necessary; prefer `redis-cli -n 0 keys 'celery*'` to inspect before deletion.
3. Restart Celery workers to re-establish connections and reload the job cache:
   ```bash
   docker compose restart worker
   ```
4. Trigger a lightweight synthetic job submission to repopulate cache layers and ensure metrics recover:
   ```bash
   curl -X POST http://localhost:8080/jobs \
     -H "X-Api-Key: $API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"input_expression": "1+1", "context": {}}'
   ```
5. Monitor `calculator_gateway_job_queue_depth` and `calculator_gateway_jobs_enqueued_total` to verify normal traffic, and clear stale cache entries with `redis-cli -n 0 FLUSHDB` only if data corruption persists.

## Worker Scaling & Deployment

1. **Horizontal scale-out:** Run multiple Celery worker replicas pinned to the `calculator-jobs` queue. Kubernetes `Deployment` or Docker Compose `scale` can be used; ensure each worker process sets `--hostname` to surface individual heartbeat metrics.
2. **Priority lanes:** Enable tiered QoS by configuring Celery routing keys per priority level. The gateway maps the `priority` field into discrete buckets (`JobSettings.priority_levels`); provision dedicated queues (e.g., `calculator-jobs.high`, `calculator-jobs.normal`) and route via Celery's `task_routes` to guarantee latency for critical jobs. A minimal router looks like:
   ```python
   celery_app.conf.task_routes = {
       "gateway.execute_job": {
           "queue": "calculator-jobs.high",
           "routing_key": "calculator.jobs.high",
       }
   }
   ```
   Run latency-sensitive workers with `celery worker --queues calculator-jobs.high` and background pools against the default queue to prevent starvation.
3. **Autoscaling guidance:** Monitor the `gateway.job.queue_depth` Prometheus metric and Celery worker heartbeats. Trigger scale-up when queue depth exceeds 75% of `JobSettings.max_queue_size` or worker CPU saturates >80% for five minutes. Scale-down once backlog clears and concurrency utilization drops below 40%.
4. **Stateful persistence:** Postgres holds the job ledger (`jobs` table) while Redis caches in-flight/completed payloads with TTL. During deployments, drain workers gracefully (`celery -A app.task_queue control cancel_consumer`) before terminating pods to avoid losing locks on running jobs.
5. **Disaster recovery:** Restore Postgres from point-in-time backups to recover job metadata; expired Redis entries are rehydrated from the database on demand. Document fallback procedures to manually requeue jobs via `enqueue_job` if necessary.

## Backup & Recovery

* Postgres: enable WAL archiving or scheduled dumps (e.g., `pg_dump`) for API key/audit retention.
* Redis: persistence is optional. If durability is required, enable AOF/RDB snapshots or run Redis in clustered mode.
* Configuration: store `.env.production` secrets in a vault (HashiCorp Vault, AWS Secrets Manager, etc.).

## Deployment Pipeline

1. CI runs `make lint`, `make test`, Alembic migration check, and Docker image builds for gateway and evaluator.
2. Images are tagged `phase1-<sha>` and pushed to a container registry (GHCR or ECR).
3. CD applies Helm charts or Docker Compose manifests, wiring environment variables and secrets from the deployment target.
4. Canary deployment gates new versions until metrics and logs stay within SLO thresholds.

## Release Plan – phase2-alpha.1

1. **Pre-flight checks**
   * Ensure CI green (`make lint`, `make test`, docker image builds) and run the async stack locally with `make compose-up`.
   * Validate OpenTelemetry traces across enqueue → worker → completion spans in Tempo.
   * Confirm Grafana's `Gateway Overview` shows live job throughput and queue depth while submitting sample workloads.
2. **Compose validation**
   * From a clean checkout run `docker compose -f docker-compose.phase1.yml up --build`.
   * Submit at least five asynchronous jobs via `/jobs`, ensuring WebSocket notifications broadcast status updates.
   * Verify Redis queue depth drains and `calculator_gateway_jobs_failed_total` remains 0.
3. **Tagging & artifacts**
   * Bump container image tags to `phase2-alpha.1` in deployment manifests.
   * Create the git tag once validation succeeds: `git tag phase2-alpha.1 && git push origin phase2-alpha.1`.
4. **Release notes**
   * Highlight asynchronous job orchestration, Celery/Redis backbone, Prometheus job metrics, Grafana dashboards, and runbook updates.
   * Document upgrade steps (apply latest migrations, restart gateway and workers, ensure Redis broker at required version).
5. **Rollout monitoring**
   * Watch `calculator_gateway_job_queue_depth` and `jobs_in_progress` for 30 minutes post deploy.
   * Keep an eye on failure counters; revert tag if failure rate >5% or queue depth remains above 80% for 15 minutes.
