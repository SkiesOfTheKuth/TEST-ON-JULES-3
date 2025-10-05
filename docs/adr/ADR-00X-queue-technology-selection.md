# ADR-00X: Queue Technology Selection

## Status
Accepted

## Context
Phase 2 of the calculator platform requires asynchronous job processing with visibility into queue depth, execution latency, and retry behaviour. The solution must integrate with existing Python services, expose Prometheus metrics, and support OpenTelemetry tracing with bounded attributes.

## Decision
We selected **Celery** with a **Redis** broker and result backend.

- Celery offers first-class Python integration, solid retry semantics, and fine-grained signal hooks that we extend for tracing spans ("jobs.enqueue" → "jobs.execute") and Prometheus metrics (jobs_enqueued_total, jobs_in_progress, queue_depth, worker runtime histograms).
- Redis is already part of the platform for caching and WebSocket fan-out; reusing it for the broker keeps latency low and simplifies local development. It supports priority queues, pub/sub notifications, and snapshotting (RDB/AOF) covered in the runbooks.
- The combination allows strict control over attribute cardinality and context propagation (traceparent headers + x-enqueued-at-ms) without introducing new infrastructure.

## Consequences
- We must maintain Celery worker lifecycle runbooks (scale out/in, purge, revoke, priority routing).
- Redis availability directly affects job orchestration; backups and restore procedures are mandatory.
- Future migrations to a multi-tenant broker (e.g., RabbitMQ, Kafka) would require new instrumentation and provisioning but can reuse the established tracing and metrics contracts.
