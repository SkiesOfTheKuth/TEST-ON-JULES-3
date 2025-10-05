# ADR-004: Queue Technology for Asynchronous Jobs

* **Status:** Accepted
* **Date:** 2025-02-10

## Context

Phase 2 introduces asynchronous job orchestration for the calculator platform. We need a task queue that can:

* Integrate with the existing FastAPI gateway with minimal operational overhead.
* Support delayed execution, retries with backoff, and visibility into worker state.
* Run within the Phase 1 deployment footprint (Docker Compose today, Kubernetes later) without requiring dedicated broker clusters beyond Redis/Postgres already provisioned.
* Expose hooks for observability so that Phase 1 OpenTelemetry and Prometheus instrumentation can extend across enqueue → execution → completion.

Candidate technologies evaluated:

* **Celery (Redis broker):** Mature, Python-native, battle-tested retry semantics, task introspection via `celery inspect`, large ecosystem of monitoring tools. Native support for custom instrumentation and pluggable serializers.
* **Arq:** Lightweight asyncio-focused queue that speaks Redis directly. Small dependency footprint but limited ecosystem for worker management, introspection, and scheduling.
* **RQ:** Simple to operate (Redis only) but lacks native retry backoff, rate limits, or built-in task progress reporting without third-party extensions.
* **RabbitMQ + Celery:** Provides strong delivery guarantees but introduces an additional broker to provision, monitor, and secure.

## Decision

Adopt **Celery with Redis** as the task orchestrator, embedding it inside the gateway service for now. Key reasons:

1. **Operational reuse:** Redis is already part of the Phase 1 stack. Celery can share the broker for both task dispatch and job cache metadata, avoiding new infrastructure.
2. **Rich lifecycle controls:** Celery exposes retries, acks late, task revocation, rate limiting, and worker pools—requirements for sandboxed evaluations that may time out or need replay.
3. **Observability hooks:** Celery surfaces task signals that map cleanly to OpenTelemetry spans and Prometheus counters. The instrumentation in `task_queue.py` emits queue depth, in-progress gauges, and runtime histograms without custom forks.
4. **Future scalability:** As we move toward Kubernetes, Celery's worker autoscaling patterns (`control add_consumer`, `cancel_consumer`, `pool_grow/shrink`) align with HPA and KEDA integrations.

Arq and RQ were rejected because they would require building missing retry/backoff primitives ourselves and lack the diagnostic tooling expected for Phase 2. RabbitMQ was deferred because adding and operating a second broker would slow delivery and complicate disaster recovery without delivering compelling benefits at our current scale.

## Consequences

* The gateway now depends on Celery worker processes; deployments must start the worker pool alongside the FastAPI application.
* Redis availability becomes even more critical—runbook updates cover cache rebuilds and queue purges after broker outages.
* Developers should familiarize themselves with Celery CLI tooling (`inspect`, `control`, `purge`) and the metrics emitted (`jobs_enqueued_total`, `job_queue_depth`, etc.).
* The architecture leaves room to extract the task orchestrator into its own service later; the ADR captures the rationale should future requirements favor an alternate broker.
