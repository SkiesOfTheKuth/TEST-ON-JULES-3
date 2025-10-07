"""Pydantic schemas for API contracts."""

from __future__ import annotations

import datetime as dt
import hashlib
import re
from enum import Enum
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class SymbolicOperation(str, Enum):
    SIMPLIFY = "simplify"
    DERIVATIVE = "derivative"
    INTEGRAL = "integral"
    SOLVE = "solve"
    SERIES = "series"
    CODEGEN = "codegen"


class SymbolicContextPayload(BaseModel):
    variables: Dict[str, Any] = Field(default_factory=dict)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class SymbolicCodegenOptions(BaseModel):
    targets: list[str] = Field(default_factory=lambda: ["python"])
    human_readable: bool = True


class SymbolicJobRequest(BaseModel):
    operation: SymbolicOperation
    expression: str = Field(..., min_length=1, max_length=1024)
    variable: Optional[str] = None
    order: Optional[int] = Field(default=None, ge=1)
    context: SymbolicContextPayload = Field(default_factory=SymbolicContextPayload)
    codegen: SymbolicCodegenOptions = Field(default_factory=SymbolicCodegenOptions)


class JobSubmissionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    input_expression: str = Field(..., min_length=1, max_length=512)
    context: Dict[str, float] = Field(default_factory=dict)
    priority: int = Field(0, ge=0)
    tags: list[str] = Field(default_factory=list)
    task_type: Optional[Literal["standard", "heavy", "gpu", "symbolic"]] = None
    requires_gpu: bool = False
    estimated_runtime_ms: Optional[int] = Field(default=None, ge=1)
    mode: Literal["arithmetic", "symbolic"] = "arithmetic"
    symbolic: Optional[SymbolicJobRequest] = None

    @model_validator(mode="after")
    def validate_symbolic_mode(self) -> "JobSubmissionRequest":
        if self.mode == "symbolic":
            if self.symbolic is None:
                raise ValueError("symbolic payload is required when mode='symbolic'")
            if self.task_type is None:
                self.task_type = "symbolic"
        else:
            if self.symbolic is not None:
                raise ValueError("symbolic payload must not be provided when mode='arithmetic'")
        return self


class JobPolicyStatus(BaseModel):
    enforced: bool = False
    violations: list[str] = Field(default_factory=list)
    snapshot: Dict[str, Any] = Field(default_factory=dict)
    decision_reason: Optional[str] = None
    queue_decision: Optional[str] = None


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant: str
    status: str
    created_at: dt.datetime
    started_at: Optional[dt.datetime] = None
    completed_at: Optional[dt.datetime] = None
    priority: int
    requested_priority: int
    tags: list[str] = Field(default_factory=list)
    queue_name: str
    task_type: str
    mode: Literal["arithmetic", "symbolic"] = "arithmetic"
    symbolic_cache_key: Optional[str] = None
    symbolic_request: Optional[Dict[str, Any]] = None
    verification_passed: Optional[bool] = None
    verification_error: Optional[str] = None
    estimated_runtime_ms: Optional[int] = None
    policy: JobPolicyStatus = Field(default_factory=JobPolicyStatus)
    links: Dict[str, str] = Field(default_factory=dict)


class JobResultResponse(JobStatusResponse):
    result_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
