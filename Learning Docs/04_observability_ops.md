# 04 Observability and Operations

Last Updated: 2025-10-08 (commit 59cb599)

## Metrics
- **Gateway Prometheus endpoint**: http://localhost:8080/metrics
  - calculator_gateway_http_requests_total ? HTTP request count by route/method.
  - calculator_gateway_job_queue_depth ? per-queue depth gauge (labels: queue).
  - calculator_gateway_job_duration_seconds ? histogram for worker turnaround.
  - calculator_gateway_policy_decisions_total ? allow/deny/override counts.
  - calculator_gateway_autoscale_events_total ? scale up/down events.
  - calculator_gateway_symbolic_cache_hits_total ? hit/miss metrics.
- **Worker metrics**: Exported via Prometheus client embedded in Celery tasks.
- **Symbolic engine metrics**: OTEL spans with operation name, execution time,
  and sandbox duration (pushes to Tempo/Prometheus when OTEL endpoint configured).

## Tracing
- OpenTelemetry exporters configured via app/instrumentation.py.
- Spans include attributes:
  - calculator.job_id
  - calculator.queue_name
  - calculator.policy_outcome
  - calculator.symbolic.cache_state
  - calculator.retry_count
- Tempo collects traces; Grafana data source pre-configured (see observability/tempo.yaml).

## Logging
- Structured JSON logs using python-json-logger with fields: timestamp, level,
  request_id, trace_id, tenant, endpoint, policy outcome, queue.
- Loki stack in compose receives logs via promtail.
- Gateway logs note symbolic verification mismatches and policy violations.

## Dashboards
- Stored under observability/grafana/dashboards/.
  - gateway-overview.json: request health, latencies, error budget burn-down.
  - phase2-queue.json: queue depth, throughput, autoscale decisions.
  - worker-health.json: heartbeat, wait histograms, failure reasons.
  - phase3-symbolic.json: symbolic request volume, cache hit ratio,
    verification outcomes, sandbox duration percentiles.
- When editing dashboards in Grafana, export JSON and commit with changelog note.

## Alerts/SLOs
- Prometheus rules (not yet versioned) monitor:
  - p95 queue wait < 5s.
  - Failure ratio < 5%.
  - Worker CPU < 85% sustained.
- To add new alerts, document them here with thresholds and runbook link.

## Runbooks (Quick Index)
- docs/OPERATIONS.md sections cover:
  - Celery worker lifecycle (deploy, drain, rollback).
  - Redis outage recovery.
  - Policy engine tuning.
  - Dashboard interpretation.
- Add bulletproof steps here whenever runbooks receive major revisions.

## Why This Stack
- Prometheus/Grafana chosen for ubiquity, container-friendly deployment, and
  existing tooling support.
- Tempo/Loki pair integrates seamlessly with Grafana for traces/logs; open-source
  alternative to hosted services.
- Structured logging reduces time-to-triage for policy violations and queue
  anomalies.

## Update Checklist
- Record new metrics names and label conventions.
- Note any changes to alert thresholds or SLOs.
- Add new dashboards to this index with purpose and location.
- Update Last Updated with commit reference after modifications.

## Open Questions
- Should we automate validation of Grafana dashboards (e.g., regression tests on
  JSON schema)?
- Do we need long-term trace storage beyond Tempo when Phase 5 adds compliance
  reporting?
