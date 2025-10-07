"""Schemas for the gateway symbolic solve endpoint."""

from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


class SymbolicSolveRequest(BaseModel):
    expr: str = Field(..., min_length=1, max_length=2048)
    subs: Optional[Dict[str, float]] = None
    mode: Literal["symbolic"] = "symbolic"


class SymbolicSolveResponse(BaseModel):
    ok: bool
    result: Optional[Dict[str, object]] = None
    error: Optional[str] = None
    metadata: Dict[str, object] = Field(default_factory=dict)
