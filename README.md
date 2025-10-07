# Calculator Platform - Phase Roadmap Status

## Overview
This repository tracks the calculator platform as it graduates from Phase 1 hardening into the Phase 2 distributed compute backbone described in `docs/ROADMAP.md`. The Phase 2 stack now includes real FastAPI + Celery services, Redis/Postgres persistence, multi-lane workers, per-tenant policy enforcement, WebSocket notifications, and a CI pipeline that exercises lint, unit, integration, and optional load tests.

- Observability updates: refreshed Grafana dashboards (Gateway Overview, Phase 2 Queue Lanes, Worker Health) and new runbooks covering worker lifecycle, Redis recovery, policy tuning, and dashboard interpretation.

## Delivery Status
- **Baseline Alignment (Weeks 0-1)** – Done. Repo hygiene, migrations, auth enforcement, rate limiting, and observability scaffolding merged.
- `services/symbolic_engine`  SymPy-powered symbolic microservice with sandboxed HTTP API, Redis result cache, and Prometheus metrics.
- **Phase 1 – Hardened Core Services (Weeks 2-4)** – Ongoing. Gateway/evaluator split ships with traces, metrics, and sandboxing. Outstanding: chaos/fuzz/load coverage and remaining sandbox hardening tasks.
- **Phase 2 – Distributed Compute Backbone (Weeks 5-8)** – Complete. Celery orchestrator, heavy/GPU lanes, tenant policies, autoscaling runbooks, Grafana dashboards, and CI/CD validation are live.
- **Phases 3-6** – Not started; roadmap items tracked in documentation.

## Immediate Next Actions
1. Close remaining Phase 1 hardening gaps (chaos, fuzzing, deeper sandbox security) before expanding to symbolic workloads.
2. Plan Phase 3 symbolic engine work now that distributed execution, policies, and observability are stable.
3. Continue updating `docs/ROADMAP.md`, `docs/OPERATIONS.md`, and `docs/CHANGE_LOG.md` alongside code changes. CI enforces the changelog requirement via `scripts/ensure_changelog_updated.py`.

## CI / Validation Pipeline
- Workflow: `.github/workflows/phase1-ci.yml` (Phase 2 CI/CD) runs on push/PR.
- Stages:
  - `lint-unit`: installs via Poetry, runs `make lint` and `make unit` (gateway + evaluator coverage uploaded).
  - `integration`: spins up `docker-compose.phase2.yml`, applies migrations, seeds API keys, executes `pytest tests/integration -m integration` against live Redis/Celery/Postgres.
  - `load-test` (optional): runs Locust smoke test when triggered (label `run-load-tests`, workflow dispatch, or push to `main`). Thresholds for p95 latency, RPS, and failure ratio are enforced.
- Changelog enforcement: PRs without `docs/CHANGE_LOG.md` updates fail the `Ensure change log updated` step unless `ALLOW_MISSING_CHANGELOG` is explicitly set.

## Documentation Duties
- Follow `docs/DOCUMENTATION_MAINTENANCE.md` for every change (identify impacted docs, update changelog, validate instructions).
- Automated or programmatic contributors must read `INSTRUCTIONS/AGENT_DOCS_CHECKLIST.md` before making changes.
- Grafana dashboards and runbooks for new metrics live under `observability/`; export updates as JSON when panels change.

## Repo Map
- `services/gateway` – FastAPI gateway, Celery orchestration, policy engine, tests (unit + integration), scripts.
- `services/symbolic_engine` – FastAPI service running SymPy workloads in a subprocess sandbox with Redis caching and `/v1/symbolic` endpoint.
- `services/safe_evaluator` – Sandbox service, allowlist management, telemetry.
- `libs/` – Shared calculator logic packages consumed by the gateway/evaluator.
- `docs/` – Roadmap, operations, security, architecture, maintenance guide.
- `observability/` – Grafana dashboards, Prometheus config, Tempo/Loki provisioning.
- `tests/load` – Locust performance harness with configurable thresholds.

## Helpful Commands
- `make compose-phase2-up` / `make compose-phase2-down` – Launch or stop the full Phase 2 stack.
- `make integration` – CI parity spin-up + integration suite.
- `API_KEY=<key> make load-test` – Run Locust against the async job API (thresholds enforced).
- `poetry -C services/gateway run python scripts/autoscale_workers.py --queue-depth 120 --active-workers 3` – Evaluate autoscaling decisions (pass `--apply` to grow/shrink worker pools).

Keep this README aligned with roadmap status, CI guarantees, and operational expectations as the platform advances toward Phase 3.