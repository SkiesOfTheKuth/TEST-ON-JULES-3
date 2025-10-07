# 02 Services and Modules

Last Updated: 2025-10-07 (commit a6e34c0)

## Gateway (services/gateway)
- **Role**: API gateway, job orchestrator, policy gatekeeper, metrics exporter, WebSocket notifier.
- **Entry point**: pp/main.py (FastAPI app + lifespan hooks pending refactor).
- **Key modules**:
  - pp/config.py: Pydantic settings for database, Redis, Celery, policy, autoscale, symbolic integration.
  - pp/models.py: SQLAlchemy ORM (API keys, jobs, quotas, tenant policies, symbolic cache entries).
  - pp/policy.py: Loads tenant policy snapshots, enforces queue access, bans, runtime ceilings.
  - pp/task_queue.py: Celery app factory, metrics instrumentation, worker task definitions, failover handlers.
  - pp/jobs.py: Job creation, serialization, cache helpers, WebSocket broadcast.
  - pp/symbolic_client.py: REST/gRPC client for symbolic engine with retry/backoff, verification helper.
  - pp/autoscale.py: Decision helper for manual or automated scaling.
  - pp/time_utils.py: Centralised timezone-aware timestamp helper (UTC).
- **Config surface**: .env.* feed Pydantic settings; secrets manageable via environment variables in container/k8s.
- **Why this split**: Keeps HTTP concerns, data model, queue orchestration, and policy logic modular so unit tests can stub each piece.

## Safe Evaluator (services/safe_evaluator)
- **Role**: Hardened execution sandbox for arithmetic expressions.
- **Tech**: gRPC server (grpcio), uses libs/calculator_core for AST validation and controlled execution.
- **Security**: Whitelists AST nodes, enforces runtime budgets via multiprocessing/timeouts, collects telemetry for each evaluation.
- **Update hooks**: If evaluator allowlist changes, sync docs (docs/OPERATIONS.md) and symbolic fallback expectations.

## Symbolic Engine (services/symbolic_engine)
- **Role**: Exposes SymPy operations (simplify, derivative, integral, solve, series, code-gen) via FastAPI.
- **Structure**:
  - pp/main.py: FastAPI router, health endpoints, /symbolic/compute handler.
  - pp/operations.py: Implementation of supported symbolic operations, optional Numba acceleration.
  - pp/sandbox.py: Subprocess worker enforcing timeout/memory limits.
  - pp/models.py: Pydantic request/response schemas (operation enum, context, code generation options).
  - Tests under 	ests/ cover API responses, sandbox behaviour, and edge cases.
- **Deployment**: Standalone Dockerfile; included in docker-compose.phase2.yml with dedicated Celery worker worker-symbolic.
- **Why separate service**: Allows tuning runtimes/resources independent from arithmetic workers, isolates heavier dependencies, keeps gateway lean.

## Shared Libraries (libs/)
- calculator_core: AST guard, sandbox runner, allowlist definitions, powering evaluator and symbolic sandbox.
- calculator_logic: Shared business logic reused by gateway workers.
- Path-based dependencies registered in gateway Poetry config for editable installs.

## Infrastructure Modules
- **Celery**: Configured in pp/task_queue.py; routing maps to queues (calculator-jobs, calculator-jobs-heavy, calculator-jobs-gpu, calculator-jobs-symbolic).
- **Postgres migrations**: Alembic revisions in services/gateway/alembic/versions. lembic/script.py shim exists for lightweight unit tests.
- **Redis caches**: pp/cache.py centralises Redis namespaces (job metadata, symbolic cache, policy cache).
- **Observability**: pp/instrumentation.py wires OpenTelemetry tracing, Prometheus metrics (via Instrumentator), and structured logging.
- **Protos**: services/protos/symbolic_engine.proto defines gRPC contract stub for future binary transports (currently REST).

## Why These Dependencies
- **Poetry workspace per service**: isolates dependency graphs, keeps lockfiles accurate, and ensures reproducible builds for each image.
- **Dataclasses + Pydantic**: dataclasses for internal metadata (smaller footprint), Pydantic for external API validation and type coercion.
- **Async SQLAlchemy**: fits Celery/gateway concurrency model; future-proofs for read replicas, connection pooling.
- **Prometheus instrumentation**: industry-standard metrics for queue depth/autoscale; easier to integrate with Grafana than bespoke logs.

## Update Checklist
- Add new modules or services to this guide with purpose, structure, and rationale.
- Update queue list if new Celery routes appear.
- Link to ADRs when major technology decisions change.
- Refresh Last Updated footer when edits occur.

## Open Questions
- Should symbolic engine expose a gRPC interface to reduce HTTP overhead for large payloads?
- When Phase 4 arrives, do we split WebSocket collaboration into its own service or extend gateway?
