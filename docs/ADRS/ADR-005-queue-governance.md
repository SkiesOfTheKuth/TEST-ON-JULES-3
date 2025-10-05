# ADR-005: Queue Taxonomy and Policy Governance

- **Status:** Accepted
- **Date:** 2025-10-06

## Context

Phase 2 introduces multi-lane execution for calculator jobs. We must expose heavy/GPU queues without breaking existing clients, record policy decisions for auditing, and leave room for autoscaling guidance. Tenants require guardrails (disallowed operations, quota overrides) and we need cache-aware evaluation so policy changes apply immediately.

Key drivers:

- Standard jobs must remain low-latency while heavy workloads run in parallel.
- GPU submissions may be optional per tenant and should fail fast when the policy forbids them.
- Observability needs per-queue metrics and policy decision traces for SRE runbooks.
- Policies and queues should be stored centrally (Postgres) but cached (Redis) for read performance.

## Decision

We standardise on three Celery queues: calculator-jobs (default), calculator-jobs-heavy, and calculator-jobs-gpu. The gateway's policy engine evaluates each submission and returns the queue name, task type, priority, and policy snapshot. Routing happens inside enqueue_job, and Celery metrics record queue-specific counters, queue depth, and worker CPU gauges.

Per-tenant policies live in a new 	enant_policies table with JSON fields (llowed_queues, anned_patterns, policy_snapshot) and feature flags (llow_heavy, llow_gpu). Results are cached in Redis (policy:<tenant>). When policies change, operators flush the cache key to refresh decisions.

Autoscale guidance uses the same queue taxonomy. AutoscaleObservation and evaluate_autoscale compute desired worker counts from queue depth, p95 wait, CPU, and cooldown timers. The scripts/autoscale_workers.py helper can dry-run or apply scaling commands.

## Consequences

- API responses now include queue_name, 	ask_type, policy metadata, and equested_priority to aid clients.
- Additional migrations create 	enant_policies and extend the jobs table with governance fields.
- Tests and fixtures mock policy evaluation, queue routing, and autoscale behaviour.
- Operations runbooks (docs/OPERATIONS.md) describe policy editing, cache invalidation, autoscale thresholds, and queue-specific metrics.
- Future Phase 3 features (symbolic engine, workspace) can leverage the same policy/queue infrastructure without revisiting routing.

