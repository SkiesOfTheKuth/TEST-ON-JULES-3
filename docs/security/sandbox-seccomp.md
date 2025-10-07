# Symbolic Engine Seccomp Notes

This placeholder documents the next steps for enforcing Linux seccomp around the symbolic engine sandbox:

1. Define a libseccomp profile that permits only the syscalls required by CPython + SymPy (openat for imports, read/write, clock/time, futex, mmap/munmap, prlimit). Block filesystem mutation (`unlink`, `chmod`, etc.) and networking syscalls.
2. Ship the profile as a JSON or C-based BPF program checked into this directory. Provide a loader utility that the sandbox runner can invoke before executing user expressions.
3. Extend `sandbox_runner.py` to load the profile (via `seccomp` or `prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ...)`) once the limits are in place. Ensure failures fall back to a clear error so that requests can be retried or rejected gracefully.
4. Update integration tests to exercise seccomp-enabled execution and capture metrics indicating whether seccomp is active.

Until the profile is finalized, the service documents this TODO and relies on the existing resource limits + import denylist.
