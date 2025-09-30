# OPERATIONS

## Runbooks

### Elevated error rates on `/calculate`
1. Check rate limiting metrics for surges (`429` count, latency).
2. Inspect structured logs for repeated `unauthorized` or `Invalid expression` events.
3. Validate API key rotations and limiter backend availability.
4. If abuse is detected, raise limits for trusted CIDRs only or rotate credentials.

### Evaluator timeout alerts
1. Confirm resource utilization on workers (CPU saturation).
2. Review expression payloads for abnormally large inputs.
3. Adjust `CALCULATOR_MAX_RUNTIME_SECONDS` cautiously (<= 0.25s) and redeploy.
4. Consider scaling horizontally or adding queue if sustained load continues.

### Deployment rollback
1. Identify the previous green build artifact.
2. Deploy using `docker run` or orchestrator-specific rollback command.
3. Validate health check responses and smoke tests.
4. Announce rollback completion and open incident RCA ticket.

## Observability
- Logs: JSON to stdout, ingest into ELK/OpenSearch or Cloud Logging.
- Metrics: scrape `/metrics` for Prometheus-compatible counters/histograms (`calculator_http_requests_total`, `calculator_http_request_duration_seconds`, `calculator_evaluations_total`).
- Health: `/healthz` for liveness, `/readyz` for readiness used by orchestrator probes.
- Tracing: add OpenTelemetry `FlaskInstrumentor` once backend configured.

## On-call Checklist
- API uptime ≥ 99.5% monthly.
- P95 latency < 300 ms.
- Unauthorized attempts < 5% of total traffic.
