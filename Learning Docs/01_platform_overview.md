# 01 Platform Overview

Last Updated: 2025-10-07 (commit a6e34c0)

## Mission Statement
Deliver a multi-tenant, zero-trust calculator platform that supports synchronous
API calls, asynchronous job orchestration, symbolic computation, collaborative
workspaces, and AI assistance while meeting production-grade DevSecOps
standards.

## What Exists Today
- **Phase 1 (Hardened Core)**: Flask prototype replaced by FastAPI-based gateway
  with SafeEvaluator gRPC service, API key enforcement, per-IP throttles, and
  strict expression sandboxing.
- **Phase 2 (Distributed Backbone)**: Celery orchestrator with Redis broker,
  Postgres job ledger, multi-lane worker pool (standard, heavy, GPU), policy
  engine, autoscaling guidance, WebSocket notifications, and full observability
  stack (Prometheus, Tempo, Loki, Grafana).
- **Phase 3 (Symbolic Engine, in progress)**: Dedicated SymPy + FastAPI
  microservice, gateway-level symbolic routing and caching, verification hooks,
  proto definitions, and CI/compose integration.

## Guiding Principles
1. **Secure by default** ? API key auth, policy checks, quotas, sandboxing, and
   audit logging are treated as first-class features.
2. **Async first** ? All heavy computation runs as queueable jobs with retries
   and cached results; synchronous /calculate remains for quick work.
3. **Observability everywhere** ? Metrics, traces, and structured logs instrument
   every stage (client -> gateway -> worker -> notification).
4. **Documentation parity** ? Any behavioural change requires updates to
   roadmap, operations guide, changelog, and now this learning series.
5. **Composable services** ? Each capability is a deployable unit (gateway,
   evaluator, symbolic engine, workers) built for containerized or K8s
   environments.

## Capability Map
| Capability | Owner | Notes |
|------------|-------|-------|
| Sync evaluation | Gateway -> SafeEvaluator | HTTP /calculate forwards to gRPC sandbox for rapid expressions. |
| Async jobs | Gateway -> Celery -> Workers | /jobs POST stores payload, enqueues task, tracks lifecycle, notifies via WebSocket. |
| Policy & quotas | Gateway service | Tenant-level queue access, runtime caps, banned patterns, per-tenant quotas backed by Postgres/Redis. |
| Symbolic compute | Gateway -> Symbolic Engine | mode=symbolic jobs route to new microservice; results cached in Redis/Postgres. |
| Observability | Prometheus, Tempo, Grafana, Loki | Metrics endpoints plus dashboards for queues, workers, autoscale, policy outcomes. |
| CI/CD | GitHub Actions (phase1-ci.yml) | Lint, unit, compose-backed integration, optional Locust load stage; changelog enforcement. |

## Why This Architecture (Versus Alternatives)
- **FastAPI + Celery**: lightweight async framework and mature distributed task
  queue. Alternatives like Arq or RQ lacked multi-queue routing, retry policies,
  or enterprise-level tooling without additional effort. (See
  docs/ADRS/ADR-0005-symbolic-engine-technology.md for queue comparisons.)
- **Redis + Postgres combo**: Redis delivers low-latency queue/cache semantics,
  while Postgres provides durable job metadata, API keys, policy persistence, and
  auditing. Removing either would complicate latency or durability guarantees.
- **SymPy + Numba**: balances feature-rich symbolic manipulation with the option
  for numeric acceleration. CAS alternatives (GiNaC, Sage) introduce heavier
  dependencies and licensing friction.
- **Microservice split**: Isolating evaluator and symbolic workloads keeps the
  gateway attack surface small and enables per-service scaling, resource limits,
  and sandboxing tuned to use-case.

## Update Checklist
When major features land, update:
- Capability map to reflect new services or responsibilities.
- Phase summary timeline with completion dates.
- Rationale section if new ADRs alter technology choices.
- Last Updated footer (include commit hash).

## Open Questions
- When should we promote the symbolic engine to GA (what SLAs are required)?
- Do we need a message bus beyond Redis when Phase 4 collaboration lands?
