"""Pydantic schemas for API contracts."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class JobSubmissionRequest(BaseModel):
    input_expression: str = Field(..., min_length=1, max_length=512)
    context: Dict[str, float] = Field(default_factory=dict)
    priority: int = Field(0, ge=0)
    tags: list[str] = Field(default_factory=list)


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    created_at: dt.datetime
    started_at: Optional[dt.datetime] = None
    completed_at: Optional[dt.datetime] = None
    priority: int
    tags: list[str] = Field(default_factory=list)


class JobResultResponse(JobStatusResponse):
    result_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
