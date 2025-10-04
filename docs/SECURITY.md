# Security Overview

## Threat Model

| Threat | Mitigation |
| ------ | ---------- |
| Expression injection (accessing Python internals) | AST validation denies disallowed nodes, the sandbox whitelist only exposes deterministic math helpers, and attribute access is explicitly blocked. |
| Long-running or resource-intensive expressions | Sandbox uses subprocess with CPU/memory limits (`resource.setrlimit`) and enforces per-request deadlines from the gateway (250 ms default). |
| Credential compromise | API keys are stored hashed (SHA-256) in Postgres, transmitted via HTTPS (to be enabled in front of gateway), and rotated via Alembic seed scripts. |
| Abuse/DoS | Redis sliding window rate limits per key and per IP; quotas table enables future tenant-level ceilings; cached deterministic results reduce evaluator load. |
| Data tampering | Audit log entries persist hash of expression + key + outcome; Postgres provides transaction durability and can be replicated. |
| Lateral movement between services | gRPC transport uses an internal network; future phases can enable mTLS by replacing `insecure_channel` with certificate-backed channels. |

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
- [ ] Configure mTLS between gateway and evaluator when production certificates are available.
- [ ] Integrate Trivy/Snyk into CI to scan Docker images.
- [ ] Add policy engine (OPA) for tenant-specific expression restrictions.

## Incident Response Notes

* Rate limit breaches: check Redis keys `rate:key:<id>` and `rate:ip:<address>` for saturation.
* Sandbox failures: inspect evaluator logs in Loki, verify `max_runtime_seconds` thresholds, and confirm host has sufficient resources.
* Data restoration: restore latest Postgres backup, repopulate Redis caches gradually to avoid thundering herds.
