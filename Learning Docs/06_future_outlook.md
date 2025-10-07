# 06 Future Outlook and Study Prompts

Last Updated: 2025-10-07 (commit a6e34c0)

## Upcoming Phases (from docs/ROADMAP.md)
1. **Complete Phase 3** ? Property/benchmark tests for symbolic workloads,
   lifespan refactor, Postgres port guard, production readiness review.
2. **Phase 4 (Collaborative Workspace)** ? Next.js client, Yjs CRDT backend,
   WebSocket gateway, role-based permissions, realtime presence.
3. **Phase 5 (Insight Agent)** ? Data lake (Kafka -> ClickHouse), RAG service,
   LLM math coach with safety guardrails, feedback loop.
4. **Phase 6 (Compliance & Deployment)** ? Helm charts, Terraform, mTLS,
   SBOM/SCA integration, multi-tenant governance, SLA runbooks.

## Skills to Focus On
- **Async distributed systems**: Understand Celery internals, retry semantics,
  idempotency strategies.
- **Observability**: Practice tracing job spans, building Grafana panels, tuning
  alerts.
- **Security**: Dive into API key hashing, policy enforcement, sandboxing.
- **Database design**: Explore migrations, job schema evolution, caching vs
  persistence trade-offs.
- **DevEx tooling**: Study how docs, changelog checks, and CI enforcement keep
  the project maintainable.

## Suggested Study Exercises
- Trace a symbolic job end-to-end: submit via curl, watch logs/metrics, inspect
  Postgres records.
- Modify 	enant_policies locally to observe policy denial paths and cache
  invalidation.
- Extend services/symbolic_engine/app/operations.py with a new SymPy function
  and wire tests/documentation following the patterns described here.
- Create a Grafana panel using calculator_gateway_symbolic_cache_hits_total to
  understand hit/miss patterns.
- Run Locust with heavier load, capture the report, and correlate with
  autoscaling decisions.

## How to Keep This Relevant
- After each phase milestone, add a short summary of what shipped, open risks,
  and recommended learning tasks.
- Link to new ADRs or design docs for deeper reading.
- Record lessons learned from incidents or resilience tests so future readers can
  study them.

## Open Questions
- Which parts of Phase 4 require new infrastructure (e.g., separate WebSocket
  cluster)?
- Do we integrate feature flag tooling before Phase 5 to manage staged rollouts?
