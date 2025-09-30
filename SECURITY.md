# Security Policy

## Supported versions

| Version | Supported |
| ------- | --------- |
| main    | ✅        |

## Reporting a vulnerability

Email security@example.com with detailed reproduction steps, affected components, and potential impact.

## Hardening checklist
- API key authentication with constant-time comparison.
- IP rate limiting enforced in-app (single-node) or at the edge (gateway/WAF).
- Sandboxed expression evaluator with runtime and magnitude guardrails.
- Strict CSP without inline scripts/styles.
- Dependencies scanned via `pip-audit` in CI.
- Secrets provided through environment variables or secret manager.

## Responsible disclosure timeline
- Acknowledge within 2 business days.
- Provide remediation plan within 5 business days.
- Target patch release within 10 business days depending on severity.
