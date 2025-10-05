# Documentation Maintenance Guide

## Purpose
Keep roadmap, architecture, operations, and usage docs in lockstep with the codebase. Any change that affects behaviour, APIs, configuration, deployment, or observability must update the relevant documentation in the same pull request.

## When to Update
- **APIs & Contracts:** New or changed REST/gRPC endpoints, CLI commands, payload fields, error codes.
- **Runtime Behaviour:** Job lifecycle, caching, security, rate limiting, evaluator logic, performance optimisations.
- **Infrastructure & Ops:** Dockerfiles, Compose/Helm manifests, environment variables, migrations, observability stack, runbooks.
- **User Journeys:** UI flows, onboarding steps, usage examples, screenshots.
- **Roadmap & Decisions:** Scope adjustments, milestone completions, technology selections (add/update ADRs).
- **Dependencies & Tooling:** Language/runtime upgrades, new build/test tools, linting/test coverage expectations.

## Update Workflow
1. Identify impacted docs before coding; note them in the issue or PR description.
2. Make the code change and edit docs side-by-side.
3. Record the change summary in `docs/CHANGE_LOG.md` (add date, area, link/PR id once opened).
4. Re-run affected examples/commands in `CALCULATOR_USAGE.txt` or service READMEs to confirm accuracy.
5. For diagrams or generated assets, update the source files under `docs/assets/` and regenerate outputs.
6. Submit docs within the same PR. If intentionally deferred, open a follow-up issue tagged `docs` before merge.

## Review Checklist
Reviewers must confirm:
- Documentation changes exist or an explicit "Docs: N/A" justification explains why.
- Instructions in `CALCULATOR_USAGE.txt`, `docs/OPERATIONS.md`, and service READMEs still work (spot-check commands).
- ADRs are added/updated for architecture-impacting changes.
- Telemetry dashboards/runbooks reflect new metrics or alerts.

## Release Duties
- Release captain compiles notes from `docs/CHANGE_LOG.md`.
- Verify all Phase roadmaps (`docs/ROADMAP.md`) mark completed milestones and link to implementation PRs.
- Archive superseded instructions under `docs/archive/<YYYY-MM>/` with a deprecation note.

## Ownership & Rotation
- Assign a quarterly "Docs Champion" to enforce the checklist and run doc audits.
- Track documentation actions with the `docs` label in issue tracker.

## Automation Hooks
- CLI/LLM agents running maintenance tasks should read `INSTRUCTIONS/AGENT_DOCS_CHECKLIST.md`.
- Future CI jobs: add make docs-lint to validate markdown, link integrity, and example commands (tracked in backlog).
- scripts/ensure_changelog_updated.py runs in CI to fail pull requests that modify code without updating docs/CHANGE_LOG.md; set ALLOW_MISSING_CHANGELOG=1 only for documented exceptions.

> **Golden rule:** if behaviour changed and the docs did not, something is wrong. Update the docs before merging.
