# Calculator Platform Roadmap

## North Star

- Deliver a multi-tenant, zero-trust calculator platform that spans interactive UI, API, job queue, symbolic engine, collaborative workspaces, and AI insights.
- Target scale: thousands of concurrent users, heavy numerical/symbolic workloads, auditable traceability, and production-grade DevSecOps.

## Baseline Alignment (Weeks 0-1)

- **Branch Merge:** land `feature/massive-improvements-3` UX/functionality onto calculator safeguards. Hand-migrate `safe_evaluator`, rate limiting, auth, metrics, and tests into the `src/` layout; resolve conflicts carefully (e.g., adapter layer wrapping `Calculator` class with guardrails).
- **Repo Hygiene:** remove `strace.log`; enforce `.gitattributes`/`.gitignore` for logs; align black/isort/ruff config; rehydrate pytest suites (CLI/GUI/API/observability).
- **Containers & Make Targets:** rebuild `Dockerfile` around `src/`, add multi-stage build, local env templates, and Make targets (`make lint`, `make test`, `make run`).
- **CI/CD Baseline:** GitHub Actions running lint + tests + docker build; push artifacts to GHCR with semantic version tags; require checks for PR merge.

## Phase 1 – Hardened Core Services (Weeks 2-4)

- **Service Split 1:** convert Flask app into API Gateway (FastAPI for async) exposing `/calculate` (sync) and `/jobs` (async).
- **Safe Evaluator Module:** containerized microservice using PyPy sandbox + fine-grained whitelist, resource-limited via multiprocessing + seccomp; gRPC interface `Evaluate(Expression, Context) -> Result|Error`.
- **Rate & Auth:** enforce JWT or API-key with HMAC rotation; integrate Flask-Limiter backed by Redis; add per-user quotas and audit logs (Postgres).
- **Observability:** OpenTelemetry instrumentation across gateway + evaluator; traces to Tempo, metrics to Prometheus, logs to Loki; dashboards in Grafana with SLOs (latency, error rate, saturation).
- **Testing:** contract tests between gateway and evaluator, chaos tests (kill sandbox mid-execution), fuzz tests for expression inputs, load test using k6.

## Phase 2 - Distributed Compute Backbone (Weeks 5-8)

**Status:** COMPLETE. Observability and runbooks delivered; production Celery stack with multi-lane routing, policy governance, autoscaling guidance, and CI validation in place (heavy-lane tuning continues).

- **Job Orchestrator:** Celery with Redis broker/backend, persistent job model, retries, metadata, and dedicated heavy/GPU workers wired via Compose.
- **API Additions:** `/jobs` POST plus `/jobs/{id}` GET and WebSocket push updates with integration coverage.
- **Task Types:** arithmetic, heavy math, and GPU lanes classified via the policy engine, routed to priority workers, and exposed through Prometheus metrics.
- **Caching Layer:** Redis result cache with TTL plus Postgres persistence for deterministic expressions.
- **Autoscaling:** decision helper, runbook guidance, and metrics-driven triggers captured alongside scripts and tests.
- **Governance:** per-tenant policies, banned operations, queue overrides, and quota integration enforced with cache invalidation.
- **Testing:** integration suite exercises multi-queue routing, policy enforcement, resilience paths, WebSocket streaming, and load thresholds.

## Phase 3 – Symbolic & Codegen Engine (Weeks 9-12)
**Status:** Workstream 1 complete � symbolic engine service scaffold, sandbox runner, Docker packaging, and contract delivered. Workstreams 2-4 (gateway integration, observability/docs, CI/load) remain outstanding.

- [x] SymbolicEngine Microservice: FastAPI + SymPy scaffolding with endpoints for simplify, derivative, integral, solve, series, and codegen.
- [x] Sandboxing: subprocess execution with timeout/memory guards (seccomp follow-up documented).
- [x] Result Types: JSON payload now includes canonical form, LaTeX, approximations, and code generation outputs.
- [x] Pipeline: Gateway routes `mode=symbolic` jobs to the symbolic service and falls back to the evaluator for arithmetic.
- [x] Caching & Verification: Redis/Postgres cache keyed by symbolic hash with optional numeric verification recorded.
- [ ] Testing: add deeper property/benchmark coverage for symbolic workloads.

## Phase 4 – Collaborative Workspace (Weeks 13-16)

- **Front-end Rewrite:** Next.js + TypeScript; integrate Chakra/Material UI; use y-websocket + Yjs for CRDT-powered shared documents.
- **Session Model:** Postgres schema for workspaces (id, owner, participants, ACL), timeline snapshots, comments, tags.
- **Real-time Infra:** WebSocket gateway (FastAPI + uvicorn) bridging Yjs docs, pushing job status updates; presence indicators, role-based permissions.
- **History & Replay:** snapshot after each commit, allow branching, diff view with highlighted expression changes and results.
- **Auth & RBAC:** integrate gateway JWT with front-end; support invite links, viewer/editor/admin roles; tie into policy engine.
- **Testing:** Cypress/Playwright end-to-end; load test Yjs sync; simulate conflict resolution; security tests for permission escalation.

## Phase 5 – Insight Agent & Knowledge Layer (Weeks 17-20)

- **Data Lake:** stream all completed jobs + explanations into Kafka; sink to ClickHouse for analytics.
- **RAG Service:** build context index (FAISS or pgvector) across past sessions, definitions, docs; create prompt builder microservice.
- **LLM Integration:** host open-source model (Llama 3 or Mistral) via LM Studio on isolated GPU node; use guardrails (prompt injection filter, output moderation).
- **Features:** natural-language step-by-step explanations, unit conversions, “what-if” scenarios, recommended next ops; voice support via Whisper/Silero for STT and Coqui or similar for TTS.
- **Feedback Loop:** collect thumbs-up/down, store in analytics for fine-tuning; implement context redaction for secrets.
- **Testing:** red-team prompts, hallucination detection, latency budget (<2s for short responses), fallback to deterministic explanations when LLM unavailable.

## Phase 6 – Compliance & Deployment (Weeks 21-24)

- **Infrastructure:** Helm charts for all services (gateway, evaluator, symbolic, workers, websocket, insight, databases, observability stack); optional Terraform for cloud (AKS/EKS).
- **Security:** integrate Snyk/Trivy scans, dependency review, SBOM generation; add network policies, mTLS between services, secrets via Vault.
- **Compliance:** audit logging (Kafka → S3), GDPR-ready data retention policies, per-tenant encryption at rest, optional customer-managed keys.
- **SLAs & Runbooks:** incident response playbooks, on-call rotation checklist, runbooks for scaling, failover, upgrades.
- **Self-Service:** Admin portal for tenants to view usage, quotas, audit logs; API for provisioning API keys/secrets.
- **Testing:** DR drills (simulate region outage), CIS benchmarks, load tests under SLA thresholds, release readiness checklist.
- **Release:** staged rollout (dev → staging → prod) with canary, feature flags, automated rollbacks.

## Implementation Notes

- **Branch Strategy:** create `epics/*` branches per phase; keep `develop` for integration; PRs gated on CI and code owners (security, ops).
- **Documentation:** maintain `ARCHITECTURE.md`, ADRs per major decision, API spec via OpenAPI, gRPC proto docs; update user guide with new flows.
- **Team Coordination:** weekly roadmap reviews, sprint planning per phase, cross-functional demos (UX, ops, AI).
- **Risk Mitigation:** early adoption of container security, LLM safety nets, overall DAG to avoid long single-threaded path (phases overlap once foundations stable).

