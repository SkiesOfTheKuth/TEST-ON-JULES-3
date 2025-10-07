# ADR-007: Symbolic Engine Sandboxing Strategy

## Status
Accepted – 2025-10-08

## Context
Phase 3 introduces a dedicated symbolic engine that evaluates arbitrary SymPy expressions supplied by end users. Running SymPy in-process exposes the gateway to arbitrary code execution, memory exhaustion, and runaway compute. We need a containment strategy that balances safety, latency, and operability for the MVP while leaving room for hardened sandboxes in a later milestone.

## Decision
- Execute every symbolic request inside a short-lived Python subprocess launched via `multiprocessing.Process`.
- Pass an allowlisted SymPy namespace (basic trig/exponential/rational helpers, constants, `Symbol`/`symbols`) and strip `__builtins__` to prevent arbitrary imports or evaluation helpers.
- Enforce a wall-clock timeout of 1.5s (`SYMBOLIC_ENGINE_TIMEOUT_SECONDS`) and terminate the worker if the expression does not complete.
- Marshal results through a `multiprocessing.Queue`, returning simplified, LaTeX, and numeric evaluation, and cache the payload in Redis for 300 seconds.
- Expose Prometheus metrics for request totals, latency, and cache hits so future hardening work has baselines.

## Consequences
- Subprocess spawning adds ~10–20ms overhead per request but gives us OS-level isolation and a straightforward kill switch on timeout.
- Redis caching keeps repeated expressions in-process and reduces the sandbox churn, which mitigates the extra fork cost.
- The MVP does not yet enforce memory cgroups or seccomp filters; runaway allocations inside SymPy could still spike RSS within the subprocess window.
- gRPC and Postgres-backed canonical caches remain out-of-scope; the HTTP interface and Redis TTL cache unblock gateway integration now while leaving room to layer persistence later.

## Alternatives Considered
- **Seccomp / gVisor containers:** Stronger syscall filtering and memory quotas but require packaging SymPy inside a container runtime or custom seccomp profile. Deferred to a follow-up once MVP telemetry lands.
- **Pyodide / WASM sandbox:** Removes native code execution entirely but carries a large startup cost and complicates numeric performance; better suited for an in-browser experience.
- **In-process AST validation only:** Cheaper to implement but still trusts SymPy internals and cannot preempt runaway evaluations.

The adopted subprocess + timeout approach gives us deterministic shutdown semantics today, instrumented telemetry, and a clear upgrade path toward container-level isolation in Phase 3 follow-ups.
