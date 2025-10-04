# Security Overview

## Threat Model

| Threat | Mitigation |
| ------ | ---------- |
| Expression injection (accessing Python internals) | AST validation denies disallowed nodes, the sandbox whitelist only exposes deterministic math helpers, and attribute access is explicitly blocked. |
| Long-running or resource-intensive expressions | Sandbox uses subprocess with CPU/memory limits (`resource.setrlimit`) and enforces per-request deadlines from the gateway (250 ms default). |
| Credential compromise | API keys are stored hashed (SHA-256) in Postgres, transmitted via HTTPS (to be enabled in front of gateway), and rotated via Alembic seed scripts. |
| Abuse/DoS | Redis sliding window rate limits per key and per IP; quotas table enables future tenant-level ceilings; cached deterministic results reduce evaluator load. |
| Data tampering | Audit log entries persist hash of expression + key + outcome; Postgres provides transaction durability and can be replicated. |
| Lateral movement between services | gRPC traffic stays on the internal bridge network and can be protected with TLS/mTLS by setting `EVALUATOR_USE_TLS=true` and providing certificate/key paths plus an optional client CA. |

## Secure Defaults

* API requests without `X-Api-Key` receive 401 responses.
* `MAX_RESULT_MAGNITUDE` (default 1e12) prevents runaway values from being cached or returned.
* Environment variables are namespaced (`GATEWAY_` / `EVALUATOR_`) to minimize accidental overlap.
* Docker images run on slim Python base images without unnecessary tooling.

## Hardening Checklist

- [x] Sandbox executes in separate process with memory/time guardrails.
- [x] Redis and Postgres run on isolated Docker network (`calc-platform-net`).
- [x] Observability stack receives structured JSON logs suitable for anomaly detection.
- [ ] Enable TLS termination on gateway (requires reverse proxy or load balancer).
- [ ] Configure mTLS between gateway and evaluator when production certificates are available (supported via `EVALUATOR_USE_TLS` and gateway evaluator TLS settings).

- [x] Integrate Trivy, Bandit, Semgrep, and Syft into CI security scanning pipelines.
- [ ] Add policy engine (OPA) for tenant-specific expression restrictions.

## Incident Response Notes

* Rate limit breaches: check Redis keys `rate:key:<id>` and `rate:ip:<address>` for saturation.
* Sandbox failures: inspect evaluator logs in Loki, verify `max_runtime_seconds` thresholds, and confirm host has sufficient resources.
* Data restoration: restore latest Postgres backup, repopulate Redis caches gradually to avoid thundering herds.
