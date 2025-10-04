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

* Grafana dashboards can be imported from `observability/dashboards/` (create folder as needed). Suggested panels:
  - Gateway request rate, p95 latency, error rate.
  - Safe evaluator duration histogram, sandbox failures.
* Tempo listens on port `4318` for OTLP traces. Ensure `GATEWAY_OBSERVABILITY__OTLP_ENDPOINT=http://tempo:4318/v1/traces` is set when running in Compose.
* Loki/Promtail collect JSON logs. Configure Grafana data sources for Prometheus, Tempo, and Loki on first launch.

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
