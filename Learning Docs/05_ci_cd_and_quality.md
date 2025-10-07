# 05 CI/CD and Quality Gates

Last Updated: 2025-10-07 (commit a6e34c0)

## Workflow Overview
- **Primary pipeline**: .github/workflows/phase1-ci.yml
  1. **lint-unit**: installs Poetry envs, runs make lint and make unit.
  2. **integration**: boots docker-compose stack (gateway, evaluator, workers,
     Redis, Postgres, observability), applies migrations, seeds API key, executes
     integration pytest suite.
  3. **load-test (optional)**: Locust smoke behind manual trigger or un-load-tests label.
  4. **Ensure changelog**: invokes scripts/ensure_changelog_updated.py to block
     PRs that skip docs/CHANGE_LOG.md.

## Local Parity Commands
- make lint -> ruff on gateway + evaluator.
- make unit -> gateway/evaluator pytest (excludes integration).
- make integration -> compose stack + integration suite (same as CI).
- API_KEY=<key> make load-test -> Locust headless run with thresholds.

## Test Suites
- **Unit**:
  - 	ests/ (repo root) ? evaluator sandbox, AST guard, rate limiting.
  - services/gateway/tests ? policies, jobs, resilience, symbolic cache, endpoints.
  - services/symbolic_engine/tests ? API, operations, sandbox.
- **Integration** (services/gateway/tests/integration):
  - Queue routing across all lanes.
  - Policy allow/deny paths.
  - WebSocket event stream.
  - Resilience scenarios (retry storms, slow worker, redis outage simulated via
    mocks; full chaos tests pending port fix).
- **Load** (	ests/load/locustfile.py): Baseline throughput & latency budgets.

## Quality Controls
- **Changelog enforcement**: PRs fail if docs/CHANGE_LOG.md untouched and
  ALLOW_MISSING_CHANGELOG not set.
- **Docs parity**: docs/DOCUMENTATION_MAINTENANCE.md enumerates required doc
  updates per change. Agents instructed via INSTRUCTIONS/AGENT_DOCS_CHECKLIST.md.
- **Poetry lock discipline**: Each service manages its own lock file. CI fails if
  lock mismatch or unresolved dependencies.
- **Static checks**: ruff configured for Python 3.10+ with targeted rules;
  Semgrep stub available for security scans (run manually for now).

## Rationale
- GitHub Actions chosen for proximity to repo, integration with required checks,
  and ability to run docker-compose for full stack tests.
- Compose-based integration ensures parity with developer experience; Kubernetes
  manifests will follow in Phase 6 but compose remains the smoketest backbone.
- Mandatory changelog/docs updates preserve institutional knowledge and feed
  these Learning Docs.

## Update Checklist
- Document new workflow jobs or environment requirements.
- Note additional test suites (e.g., property tests, fuzzing) as they appear.
- Update references when load thresholds or tooling change.
- Refresh Last Updated metadata after edits.

## Open Questions
- Should we containerise pytest for deterministic environments on Windows?
- Do we automate dashboard export validation as part of CI?
