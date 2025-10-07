# ADR-006: Symbolic Engine Technology Choices

## Status
Accepted – Phase 3 Workstream 1

## Context
The roadmap for Phase 3 introduces a dedicated symbolic computation service. We needed a mature CAS library, a plan for JIT/LLVM acceleration, and a sandboxing approach that fits the platform's zero-trust posture.

## Decision
- Use **SymPy** as the primary symbolic manipulation engine. It provides mature APIs for simplification, calculus, series, solving, and code generation across C/Python/Fortran backends, plus integration points for `numba` and `llvmjit` when heavier acceleration becomes viable.
- Prepare for **Numba/LLVM** by exposing code generation metadata (function names, targets, canonical form) in every response. The service keeps the generated artifacts in the response payload and flags when the output is suitable for downstream JIT compilation.
- Run all symbolic work inside a dedicated **sandbox subprocess** (`sandbox_runner`). The runner applies resource limits (CPU time + address space), guards suspicious tokens, and denies high-risk imports before dispatching to SymPy. Full seccomp enforcement is deferred, but the ADR documents the next steps (shipping a libseccomp profile and wiring it into the runner) so that Workstream 2 can harden the sandbox further.

## Consequences
- The service can satisfy initial symbolic use cases immediately while leaving room for future acceleration (Numba, LLVM) without changing the API surface.
- Sandbox execution adds a subprocess hop but isolates SymPy from the main API process. Additional seccomp work is tracked for follow-up, and the runner already exposes diagnostics to help tune the limits.
- Gateway integration uses a gRPC contract (`symbolic_engine.proto`) and a client stub to keep service boundaries explicit, making it straightforward to fan out symbolic workloads from existing queues once Workstream 1 completes.
