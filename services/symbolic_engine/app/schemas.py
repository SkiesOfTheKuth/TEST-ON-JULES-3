"""Pydantic models for the Symbolic Engine service."""

from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field


class SymbolicRequest(BaseModel):
    """Request payload for symbolic evaluation."""

    expr: str = Field(..., min_length=1, max_length=2048)
    subs: Optional[Dict[str, float]] = Field(default=None)


class SymbolicResponse(BaseModel):
    """Response payload returned by the symbolic engine."""

    ok: bool
    result: Optional[Dict[str, object]] = None
    error: Optional[str] = None
