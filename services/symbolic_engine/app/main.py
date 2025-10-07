from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from opentelemetry import trace

from .config import settings
from .models import (
    SymbolicComputeRequest,
    SymbolicComputeResponse,
    SymbolicMetadata,
)
from .operations import SymbolicExecutionError, execute_symbolic_operation
from .sandbox import SandboxError, SandboxMemoryExceeded, SandboxRunner, SandboxTimeout

logger = logging.getLogger("symbolic_engine")
tracer = trace.get_tracer(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title="Symbolic Engine", version="0.1.0")
    runner = SandboxRunner(
        timeout_seconds=settings.sandbox_timeout_seconds,
        memory_mb=settings.sandbox_memory_mb,
    )

    @app.post(
        "/symbolic/compute",
        response_model=SymbolicComputeResponse,
        status_code=status.HTTP_200_OK,
    )
    def compute(request: SymbolicComputeRequest) -> SymbolicComputeResponse:
        start = time.perf_counter()
        with tracer.start_as_current_span("symbolic.compute") as span:
            span.set_attribute("symbolic.operation", request.operation.value)
            span.set_attribute("symbolic.expression.length", len(request.expression))
            if request.variable:
                span.set_attribute("symbolic.variable", request.variable)
            try:
                result = runner.run(
                    execute_symbolic_operation,
                    request.operation,
                    request.expression,
                    request.context,
                    request.variable,
                    request.order,
                    request.codegen,
                    settings.allowed_functions,
                )
            except SandboxTimeout as exc:
                span.record_exception(exc)
                logger.warning("Symbolic execution timeout", extra={"operation": request.operation.value})
                raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Symbolic execution exceeded time budget")
            except SandboxMemoryExceeded as exc:
                span.record_exception(exc)
                logger.warning("Symbolic execution memory breach", extra={"operation": request.operation.value})
                raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail="Symbolic execution exceeded memory budget")
            except SandboxError as exc:
                span.record_exception(exc)
                logger.error("Sandbox error", extra={"error": str(exc)})
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
            except SymbolicExecutionError as exc:
                span.record_exception(exc)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

        duration_ms = (time.perf_counter() - start) * 1000
        metadata = SymbolicMetadata(
            execution_ms=duration_ms,
            used_numba=settings.enable_numba,
        )
        return SymbolicComputeResponse(result=result, metadata=metadata)

    @app.get("/healthz")
    def health() -> Any:
        return JSONResponse({"status": "ok"})

    return app


app = create_app()
