"""Route bindings for symbolic solve operations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from ..clients import SymbolicEngineClient, SymbolicEngineRequestError
from ..schemas.symbolic import SymbolicSolveRequest, SymbolicSolveResponse

router = APIRouter(prefix="/v1/symbolic", tags=["symbolic"])


def get_symbolic_client(request: Request) -> SymbolicEngineClient:
    client = getattr(request.app.state, "symbolic_client", None)
    if client is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="symbolic_unavailable")
    return client


@router.post("/solve", response_model=SymbolicSolveResponse)
async def solve_symbolic(
    payload: SymbolicSolveRequest,
    client: SymbolicEngineClient = Depends(get_symbolic_client),
) -> SymbolicSolveResponse:
    try:
        upstream = await client.solve(payload.expr, payload.subs)
    except SymbolicEngineRequestError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    metadata: dict[str, Any] = {
        "mode": payload.mode,
        "cache": bool(upstream.result.get("cached")) if upstream.result else False,
    }
    return SymbolicSolveResponse(
        ok=upstream.ok,
        result=upstream.result,
        error=upstream.error,
        metadata=metadata,
    )
