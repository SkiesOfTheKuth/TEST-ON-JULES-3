# ADR-0005: Symbolic Engine Technology Selection

## Status
Accepted – 2025-10-07

## Context
Phase 3 requires higher-order mathematics (symbolic manipulation, code generation, series expansion) beyond the Phase 1/2 numerical evaluator. We must deliver a service that:
- Understands symbolic expressions, calculus, and algebraic manipulation.
- Produces canonical, LaTeX, and code-generation outputs.
- Runs safely inside sandboxed execution with resource guards.
- Integrates with existing observability patterns and cloud-native packaging.

## Decision
- Use **SymPy** as the primary symbolic algebra library. It provides mature support for calculus, solving, series expansion, and code generation (Python/C/Fortran).
- Prepare hooks for **Numba/LLVM** to accelerate numeric verification and future JIT execution, but keep acceleration optional behind configuration until profiling justifies the cost.
- Expose the engine through a **FastAPI** service. HTTP/JSON is sufficient initially; a gRPC contract (`services/protos/symbolic_engine.proto`) is defined for future low-latency integration.
- Sandbox execution via a separate Python process managed by a custom runner (timeout + memory guard). On Linux we enforce `RLIMIT_AS`; on Windows we terminate after timeout while documenting stricter guard requirements.
- Package the service as its own Poetry project with a dedicated Dockerfile, aligning with other microservices.

## Consequences
- Gateway integration can treat the symbolic engine like any other HTTP/gRPC backend, using the documented contract.
- Future work must evaluate JIT acceleration and GPU routing before enabling the `enable_numba` flag in production.
- Observability instrumentation must be added in Workstream 3 to extend spans/metrics across symbolic workflows.
- Policy/caching layers live in the gateway; this service remains stateless aside from logging and telemetry.
