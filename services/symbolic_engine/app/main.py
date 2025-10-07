"""FastAPI application exposing symbolic operations."""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .sandbox import SandboxExecutionError, run_operation
from .schemas import (
    CodegenRequest,
    DerivativeRequest,
    ErrorResponse,
    IntegralRequest,
    SandboxDiagnostics,
    SeriesRequest,
    SimplifyRequest,
    SolveRequest,
    SymbolicResponse,
)

app = FastAPI(title="Symbolic Engine", version="0.1.0")


def _build_response(data: dict) -> SymbolicResponse:
    metadata = data.get("metadata", {})
    diagnostics = data.get("diagnostics", {})
    metadata.setdefault("sandbox", diagnostics)
    return SymbolicResponse(
        result=data["result"],
        latex=data.get("latex"),
        metadata=metadata,
        canonical_form=data.get("canonical_form"),
    )


@app.exception_handler(SandboxExecutionError)
async def sandbox_error_handler(_: FastAPI, exc: SandboxExecutionError):  # type: ignore[override]
    diagnostics_data = exc.diagnostics or {}
    diagnostics = SandboxDiagnostics(
        runtime_ms=float(diagnostics_data.get("runtime_ms", 0.0)),
        module_allowlist=list(diagnostics_data.get("module_allowlist", [])),
        memory_limit_mb=int(diagnostics_data.get("memory_limit_mb", 0)),
        cpu_limit_seconds=int(diagnostics_data.get("cpu_limit_seconds", 0)),
    )
    error = ErrorResponse(detail=str(exc), diagnostics=diagnostics)
    return JSONResponse(status_code=400, content=error.model_dump())


@app.get("/healthz")
def health(settings: Settings = Depends(get_settings)) -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.post("/v1/simplify", response_model=SymbolicResponse, responses={400: {"model": ErrorResponse}})
def simplify(
    request: SimplifyRequest,
    settings: Settings = Depends(get_settings),
) -> SymbolicResponse:
    data = run_operation("simplify", request.model_dump(), settings)
    return _build_response(data)


@app.post("/v1/derivative", response_model=SymbolicResponse, responses={400: {"model": ErrorResponse}})
def derivative(
    request: DerivativeRequest,
    settings: Settings = Depends(get_settings),
) -> SymbolicResponse:
    data = run_operation("derivative", request.model_dump(), settings)
    return _build_response(data)


@app.post("/v1/integral", response_model=SymbolicResponse, responses={400: {"model": ErrorResponse}})
def integral(
    request: IntegralRequest,
    settings: Settings = Depends(get_settings),
) -> SymbolicResponse:
    data = run_operation("integral", request.model_dump(), settings)
    return _build_response(data)


@app.post("/v1/solve", response_model=SymbolicResponse, responses={400: {"model": ErrorResponse}})
def solve(
    request: SolveRequest,
    settings: Settings = Depends(get_settings),
) -> SymbolicResponse:
    data = run_operation("solve", request.model_dump(), settings)
    return _build_response(data)


@app.post("/v1/series", response_model=SymbolicResponse, responses={400: {"model": ErrorResponse}})
def series(
    request: SeriesRequest,
    settings: Settings = Depends(get_settings),
) -> SymbolicResponse:
    data = run_operation("series", request.model_dump(), settings)
    return _build_response(data)


@app.post("/v1/codegen", response_model=SymbolicResponse, responses={400: {"model": ErrorResponse}})
def codegen(
    request: CodegenRequest,
    settings: Settings = Depends(get_settings),
) -> SymbolicResponse:
    data = run_operation("codegen", request.model_dump(), settings)
    return _build_response(data)
