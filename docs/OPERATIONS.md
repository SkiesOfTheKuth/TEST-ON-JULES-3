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

## Resiliency Drills

* **Evaluator crash:** Stop the evaluator container and confirm the gateway returns 503 responses and recovers once the container restarts.
* **Redis outage:** Pause the Redis container; the gateway should continue serving requests without caching but still enforce quotas from Postgres.
* **Load tests:** Use `k6` or similar to validate throughput targets. Focus on ensuring rate limits and cache hit ratios behave as expected.

## Backup & Recovery

* Postgres: enable WAL archiving or scheduled dumps (e.g., `pg_dump`) for API key/audit retention.
* Redis: persistence is optional. If durability is required, enable AOF/RDB snapshots or run Redis in clustered mode.
* Configuration: store `.env.production` secrets in a vault (HashiCorp Vault, AWS Secrets Manager, etc.).

## Deployment Pipeline

1. CI runs `make lint`, `make test`, Alembic migration check, and Docker image builds for gateway and evaluator.
2. Images are tagged `phase1-<sha>` and pushed to a container registry (GHCR or ECR).
3. CD applies Helm charts or Docker Compose manifests, wiring environment variables and secrets from the deployment target.
4. Canary deployment gates new versions until metrics and logs stay within SLO thresholds.
