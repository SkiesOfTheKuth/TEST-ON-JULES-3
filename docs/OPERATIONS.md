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
  - Gateway exposes Prometheus metrics on `:8080/metrics`, including request counters (`calculator_gateway_requests_total`), latency histograms, and a rolling gauge of rate-limit rejections per reason.
  - The evaluator publishes metrics on `:9464` covering execution duration histograms, in-flight queue depth, sandbox restart counters, and default process resource gauges.
  - Prometheus scrapes both endpoints (`observability/prometheus.yml`).
* **Logging:** Structured JSON logs with `request_id`, `trace_id`, and `span_id` are shipped to Loki via a Promtail sidecar that tails Docker logs (`observability/promtail-config.yaml`).
* **Dashboards & Alerts:** Grafana is pre-provisioned with data sources, dashboards (`Gateway Overview`, `Evaluator Health`), and alert rules. Dashboards live under `observability/grafana/dashboards/`; provisioning (data sources, alert contact points, notification policies, rules) is in `observability/grafana/provisioning/`.

> Tip: `docker compose -f docker-compose.phase1.yml up --build` launches the entire stack. Grafana is reachable on `http://localhost:3000` (admin password `grafana`).

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

## Worker Scaling & Deployment

1. **Horizontal scale-out:** Run multiple Celery worker replicas pinned to the `calculator-jobs` queue. Kubernetes `Deployment` or Docker Compose `scale` can be used; ensure each worker process sets `--hostname` to surface individual heartbeat metrics.
2. **Priority lanes:** Enable tiered QoS by configuring Celery routing keys per priority level. The gateway maps the `priority` field into discrete buckets (`JobSettings.priority_levels`); provision dedicated queues (e.g., `calculator-jobs.high`, `calculator-jobs.normal`) and route via Celery's `task_routes` to guarantee latency for critical jobs.
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
