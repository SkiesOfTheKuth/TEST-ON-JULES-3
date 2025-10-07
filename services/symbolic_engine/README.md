# Symbolic Engine Service

This service exposes advanced symbolic mathematics capabilities (simplification, differentiation, integration, solving, series expansion, and code generation) over HTTP. It underpins Phase 3 of the calculator platform roadmap.

## Features
- FastAPI application with endpoints for symbolic operations.
- Sandbox runner isolates SymPy execution in a separate process with timeout and optional memory ceiling.
- Hooks for optional Numba/LLVM acceleration in future phases.
- Structured responses including canonical expression, LaTeX, approximations, and code snippets.
- OpenTelemetry-ready; set OTLP exporter variables to emit traces/metrics.

## Local Development
```bash
poetry install
poetry run uvicorn app.main:app --reload --port 8100
```

### Tests
```bash
poetry run pytest
```

### Docker
```bash
docker build -t calculator-symbolic-engine .
```

## Settings
Environment variables mirror `app/config.py`:
- `SYMBOLIC_SANDBOX_TIMEOUT_SECONDS` (default `5.0`)
- `SYMBOLIC_SANDBOX_MEMORY_MB` (default `256`)
- `SYMBOLIC_ALLOWED_FUNCTIONS` optional comma-separated names
- `SYMBOLIC_ENABLE_NUMBA` toggles future acceleration features
- `OTEL_EXPORTER_OTLP_ENDPOINT` for telemetry export

## Roadmap Alignment
Workstream 1 delivers the service scaffold. Gateway integration, caching, and CI wiring are handled in subsequent workstreams.
