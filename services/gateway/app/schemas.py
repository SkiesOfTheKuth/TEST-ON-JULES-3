"""Pydantic schemas for API contracts."""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Optional

from pydantic import BaseModel, Field


PURE_ARITHMETIC_RE = re.compile(r"^[0-9+\-*/().\s]+$")


class ExpressionRequest(BaseModel):
    expression: str = Field(..., min_length=1, max_length=512)
    context: Dict[str, float] = Field(default_factory=dict)

    def hash(self, api_key: str) -> str:
        digest = hashlib.sha256()
        digest.update(self.expression.encode("utf-8"))
        digest.update(api_key.encode("utf-8"))
        return digest.hexdigest()

    def is_pure_arithmetic(self) -> bool:
        """Return True when the expression can be cached safely."""

        if self.context:
            return False
        return bool(PURE_ARITHMETIC_RE.fullmatch(self.expression.strip()))


class CalculationResponse(BaseModel):
    expression: str
    value: Optional[float] = None
    error: Optional[str] = None
    duration_ms: float
    from_cache: bool = False
