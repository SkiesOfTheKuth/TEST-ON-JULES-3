# Agent Documentation Checklist

Automated agents (CLI runners, cloud bots, LLM workers) must follow this playbook before and after applying changes.

## Pre-Change
1. Read `docs/DOCUMENTATION_MAINTENANCE.md` entirely.
2. List candidate docs impacted by the planned edits (architecture, operations, usage, ADRs, changelog).
3. Announce intended updates in task notes or PR description so reviewers know what to expect.

## During Change
1. Update code and docs together; do not postpone documentation.
2. When modifying behaviour, append or adjust relevant sections:
   - `docs/ROADMAP.md` for phase status.
   - `docs/OPERATIONS.md` for runbooks, metrics, deployment steps.
   - `CALCULATOR_USAGE.txt` or service READMEs for user flows.
   - `docs/ADRS/*` for design decisions.
3. Record terse but descriptive entries in `docs/CHANGE_LOG.md` (date, area, summary, PR link placeholder).

## Validation
1. Re-run documented commands (`make` targets, curl examples) to ensure they succeed.
2. Check for stale references to removed files, endpoints, or metrics.
3. Run linting/tests mentioned in the docs to confirm instructions remain accurate.

## Post-Change
1. Highlight documentation updates in the PR summary.
2. If any follow-up doc work is needed, open an issue labeled `docs` before merge.
3. Tag the "Docs Champion" (see maintenance guide) when uncertainty remains.

## Prohibited Shortcuts
- Do not claim "Docs unchanged" unless verified.
- Do not leave TODOs in docs; convert them into backlog issues.
- Do not generate large diffs of auto-written prose; keep edits targeted and reviewable.

Staying disciplined keeps human engineers and automation in sync. If you are unsure, ask before merging.
