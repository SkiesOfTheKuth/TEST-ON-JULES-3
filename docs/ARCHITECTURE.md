# Phase 2 Architecture Overview

Phase 2 extends the synchronous calculator into a distributed job platform. The FastAPI gateway now orchestrates Celery workers,
persists job state, and broadcasts live updates over WebSockets while preserving the hardened Phase 1 core.

## Service Topology

```
+------------+       +----------------------+       +----------------------+       +--------------------+
|  Clients   |  ---> |  Gateway (FastAPI)   |  ---> |   Redis (Broker &    |  ---> |  Celery Workers    |
| (REST/WS)  |       |  + Task Orchestrator |       |   Job Cache)         |       |  (Evaluator Tasks) |
+------------+       +----------------------+       +----------------------+       +--------------------+
        |                        |                            |                           |
        |                        |                            v                           |
        |                        |                      Postgres (Jobs, API Keys, Audit)  |
        |                        |                                                        |
        v                        v                                                        v
 Prometheus / Tempo / Loki  WebSocket Hub (in Gateway)                               Safe Evaluator gRPC
```

* **Gateway (FastAPI)** – exposes REST endpoints for synchronous calculations and asynchronous job submission (`/jobs`), WebSocket
  feeds (`/ws/jobs/{id}`), job metadata views, and operational health probes. It validates API keys, enforces rate & quota limits,
  writes job headers to Postgres, and seeds Redis caches before delegating work to Celery.
* **Task Orchestrator (Celery)** – embedded in the gateway package. Jobs are enqueued onto Redis-backed queues with priority lanes
  derived from `JobSettings.priority_levels`. Celery workers claim tasks, manage retries, and report lifecycle events back into the
  cache/pub-sub fabric.
* **Worker Pool** – one or more worker processes execute calculator/evaluator RPCs. They stream status transitions via Redis pub/sub
  so WebSocket clients receive near-real-time updates and metrics capture queue depth and latency.
* **Result Store & Metadata** – Postgres persists authoritative job rows (id, status, attempts, payload hashes) while Redis caches the
  serialized response envelopes with a TTL for fast repeat lookups.
* **Notification Layer** – The gateway-hosted WebSocket hub subscribes to per-job Redis channels and pushes updates to authenticated
  clients, falling back to HTTP polling if the socket closes.
* **Observability Stack** – Prometheus, Grafana, Tempo, and Loki surface queue depth, worker throughput, and end-to-end traces that span
  enqueue → worker execution → completion.

## Asynchronous Job Flow

1. Client submits a job to `/jobs` with an API key, payload, and optional priority/tags.
2. Gateway enforces quota/rate policies, persists a `queued` job row, writes the serialized payload into Redis, and publishes an initial
   update on the job’s notification channel.
3. `enqueue_job` hands the identifier to Celery with OpenTelemetry trace headers; `_record_job_enqueued` updates metrics.
4. A Celery worker locks the row, transitions the job to `running`, and invokes the evaluator gRPC service. Intermediate states are cached
   and published for WebSocket consumers.
5. On success, the worker finalizes the row with the resulting payload (`succeeded`). Failures capture the error string and leverage Celery’s
   retry/backoff facilities for transient issues.
6. Clients receive updates either by polling `/jobs/{id}` (served from Redis/Postgres) or maintaining an authenticated WebSocket subscription
   to `/ws/jobs/{id}`.

## Configuration Layers

* Environment files (`.env.development`, `.env.test`, `.env.production`) hydrate `GatewaySettings`, covering Redis brokers, priority levels,
  retry policies, and notification namespaces.
* Alembic migrations manage the Postgres schema (API keys, request audit, quotas, jobs). Redis requires no migrations but expects consistent
  namespace configuration between cache and pub/sub consumers.

## Observability

* OpenTelemetry traces span enqueue to worker completion, including evaluator RPC spans and queue depth annotations.
* Prometheus metrics (e.g., `calculator_gateway_job_queue_depth`, `calculator_gateway_job_task_runtime_seconds`) power Grafana dashboards for
  throughput, latency, and worker health. WebSocket connection counts are exported via FastAPI instrumentation.
* Loki and Tempo continue to ingest structured logs and traces from gateway and worker containers for incident correlation.

## Network Layout

* All services share the `calc-platform-net` Docker bridge network (or equivalent Kubernetes namespace). Gateway exposes port `8080` for REST
  and WebSocket traffic; Celery workers and the evaluator communicate over internal networks and gRPC port `50051`.
* Redis (broker/cache) and Postgres remain internal services. Observability endpoints (Prometheus, Grafana, Tempo) are locally exposed for
  diagnostics and load testing coordination.
