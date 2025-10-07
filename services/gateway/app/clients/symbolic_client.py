"""HTTP client for communicating with the Symbolic Engine service."""

from __future__ import annotations

from typing import Dict, Optional

import httpx

from services.symbolic_engine.app.schemas import SymbolicResponse


class SymbolicEngineRequestError(RuntimeError):
    """Raised when the symbolic engine request fails."""


class SymbolicEngineClient:
    """Thin HTTP wrapper around the symbolic engine REST API."""

    def __init__(self, base_url: str, *, timeout: float = 2.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def solve(self, expr: str, subs: Optional[Dict[str, float]] = None) -> SymbolicResponse:
        try:
            response = await self._client.post("/v1/symbolic", json={"expr": expr, "subs": subs})
        except httpx.HTTPError as exc:  # pragma: no cover - network failures
            raise SymbolicEngineRequestError(str(exc)) from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise SymbolicEngineRequestError("invalid_json") from exc
        return SymbolicResponse.model_validate(payload)

    async def aclose(self) -> None:
        await self._client.aclose()
