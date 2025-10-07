"""FastAPI application exposing symbolic evaluation operations."""

from __future__ import annotations

import os
import time
from typing import Dict, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from . import cache, metrics
from .sandbox import SandboxError, SandboxTimeoutError, run_sandbox
from .schemas import SymbolicRequest, SymbolicResponse

app = FastAPI(title="Symbolic Engine", version="0.3.0")
_TIMEOUT_SECONDS = float(os.getenv("SYMBOLIC_ENGINE_TIMEOUT_SECONDS", "1.5"))


@app.get("/healthz")
def healthcheck() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/metrics")
def metrics_endpoint() -> Response:
    payload = generate_latest()
    return Response(content=payload, media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/symbolic", response_model=SymbolicResponse)
def evaluate_symbolic(request: SymbolicRequest) -> JSONResponse:
    endpoint = "/v1/symbolic"
    start = time.perf_counter()
    ok_label = "false"
    status_code = 200
    result: Optional[Dict[str, object]] = None
    error: Optional[str] = None

    try:
        cached = cache.get(request.expr, request.subs)
        if cached is not None:
            metrics.cache_hits.labels(endpoint=endpoint).inc()
            result = dict(cached)
            result["cached"] = True
            ok_label = "true"
        else:
            payload = run_sandbox(request.expr, request.subs, timeout_s=_TIMEOUT_SECONDS)
            cache.set_result(request.expr, request.subs, payload)
            result = dict(payload)
            result["cached"] = False
            ok_label = "true"
    except SandboxTimeoutError as exc:
        status_code = 408
        error = str(exc)
    except SandboxError as exc:
        status_code = 400
        error = str(exc)
    except Exception:  # noqa: BLE001
        status_code = 500
        error = "internal_error"
        result = None
    finally:
        duration = time.perf_counter() - start
        metrics.lat.labels(endpoint=endpoint).observe(duration)
        metrics.reqs.labels(endpoint=endpoint, ok=ok_label).inc()

    response_model = SymbolicResponse(ok=error is None, result=result, error=error)
    return JSONResponse(status_code=status_code, content=response_model.model_dump())
