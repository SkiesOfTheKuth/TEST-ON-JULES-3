"""Pydantic schemas for API contracts."""

from __future__ import annotations

import hashlib
from typing import Dict, Optional

from pydantic import BaseModel, Field


class ExpressionRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=512)
    context: Dict[str, float] = Field(default_factory=dict)

    def hash(self, api_key: str) -> str:
        digest = hashlib.sha256()
        digest.update(self.expression.encode("utf-8"))
        digest.update(api_key.encode("utf-8"))
        return digest.hexdigest()


class CalculationResponse(BaseModel):
    expression: str
    value: Optional[float] = None
    error: Optional[str] = None
    duration_ms: float
    from_cache: bool = False
