# Phase 1 Architecture Overview

## Service Topology

```
+------------+      +-----------------+      +--------------------+
|  Clients   | ---> |  Gateway (API)  | ---> | Safe Evaluator RPC |
+------------+      +-----------------+      +--------------------+
        |                    |                         |
        |                    v                         v
        |              Redis (Rate)                Sandbox Runner
        |                    |
        v                    v
 Prometheus / Tempo / Loki  Postgres (Keys, Audit)
```

* **Gateway (FastAPI)** – hosts `/calculate-sync`, `/calculate`, health endpoints, and metrics. Handles authentication, rate limiting, caching, audit logging, and gRPC calls to the evaluator.
* **Safe Evaluator (gRPC)** – executes expressions in a subprocess sandbox, enforcing AST validation, runtime limits, and result magnitude caps.
* **Shared Infrastructure** – Redis provides both a cache and per-tenant sliding window limits. Postgres persists API keys, audit logs, and quota metadata. The observability stack collects traces, metrics, and logs via OTLP exporters.

## Request Flow

1. Client submits expression with `X-Api-Key` header.
2. Gateway validates key against Postgres and enforces Redis-based rate limits.
3. Gateway checks Redis cache for deterministic results.
4. Gateway invokes the safe evaluator over the `/evaluator.v1.Evaluator/Evaluate` RPC with a 250 ms deadline.
5. Safe evaluator validates AST, enforces complexity budget, and runs the expression inside a subprocess sandbox.
6. Result is returned to the gateway, cached (optional), and written to the audit log asynchronously.

## Configuration Layers

* `.env.development`, `.env.test`, `.env.production` – environment-specific overrides consumed by `pydantic-settings` classes in each service.
* Alembic maintains schema migrations for Postgres. The initial revision provisions `api_keys`, `request_audit`, and `quotas` tables.

## Observability

* OpenTelemetry SDK exports spans to Tempo (OTLP HTTP) and falls back to console output when no collector is configured.
* `prometheus_fastapi_instrumentator` exposes gateway metrics at `/metrics`; the evaluator can be scraped through OTLP exporters.
* Loki/Promtail ingest JSON-structured logs from both containers for centralized dashboards.

## Network Layout

* All services share the `calc-platform-net` Docker bridge network defined in `docker-compose.phase1.yml`.
* Gateway exposes port `8080` publicly. Safe evaluator remains internal on `50051`.
* OTLP, Prometheus, and Grafana ports are accessible locally for diagnostics.
