"""Pydantic models for the Symbolic Engine API."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Sequence

from pydantic import BaseModel, Field, field_validator


class SymbolicBaseRequest(BaseModel):
    """Common fields shared across symbolic operations."""

    expression: str = Field(..., description="Expression to process using SymPy.")
    variables: Sequence[str] = Field(
        default_factory=list,
        description="Ordered list of symbolic variables referenced by the expression.",
    )
    canonicalize: bool = Field(
        default=True,
        description="Whether to compute a canonical representation for caching.",
    )

    @field_validator("expression")
    @classmethod
    def expression_not_empty(cls, value: str) -> str:  # noqa: D417
        if not value.strip():
            msg = "Expression payload must not be empty."
            raise ValueError(msg)
        return value


class SimplifyRequest(SymbolicBaseRequest):
    method: Optional[Literal["simplify", "trigsimp", "powsimp", "expand"]] = Field(
        default=None,
        description="Optional simplification strategy. Defaults to SymPy's generic simplify.",
    )


class DerivativeRequest(SymbolicBaseRequest):
    variable: str = Field(..., description="Symbol with respect to which the derivative is taken.")
    order: int = Field(
        default=1,
        ge=1,
        le=6,
        description="Order of the derivative (1 for first derivative).",
    )


class IntegralRequest(SymbolicBaseRequest):
    variable: str = Field(..., description="Integration variable.")
    lower_limit: Optional[str] = Field(
        default=None,
        description="Optional lower limit for definite integrals.",
    )
    upper_limit: Optional[str] = Field(
        default=None,
        description="Optional upper limit for definite integrals.",
    )


class SolveRequest(BaseModel):
    equation: str = Field(..., description="Equation to solve; interpreted as equation == 0 if '=' absent.")
    variable: str = Field(..., description="Symbol to solve for.")
    parameters: Sequence[str] = Field(
        default_factory=list,
        description="Additional symbols treated as parameters (not solved for).",
    )
    canonicalize: bool = Field(
        default=True,
        description="Whether to compute canonical representation for caching.",
    )

    @field_validator("equation")
    @classmethod
    def equation_not_empty(cls, value: str) -> str:  # noqa: D417
        if not value.strip():
            msg = "Equation payload must not be empty."
            raise ValueError(msg)
        return value


class SeriesRequest(SymbolicBaseRequest):
    variable: str = Field(..., description="Expansion variable.")
    point: str = Field(
        default="0",
        description="Expansion point; parsed via SymPy sympify.",
    )
    order: int = Field(
        default=6,
        ge=2,
        le=20,
        description="Series order (number of terms including remainder order).",
    )


class CodegenRequest(SymbolicBaseRequest):
    target: Literal["c", "python", "fortran", "llvm"] = Field(
        default="c",
        description="Output language target for the generated code.",
    )
    function_name: str = Field(
        default="symbolic_kernel",
        description="Function name used during code generation.",
    )
    emit_header: bool = Field(
        default=False,
        description="Whether to emit header artifacts when supported by the backend.",
    )


class SymbolicResponse(BaseModel):
    result: str = Field(..., description="Primary symbolic result rendered as a string.")
    latex: Optional[str] = Field(
        default=None,
        description="LaTeX rendering of the symbolic result when available.",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)
    canonical_form: Optional[str] = Field(
        default=None,
        description="Canonical representation (typically SymPy srepr) for cache lookups.",
    )


class SandboxDiagnostics(BaseModel):
    """Details describing sandbox execution metadata."""

    runtime_ms: float = Field(..., description="Execution wall time in milliseconds.")
    module_allowlist: List[str] = Field(
        ..., description="Modules permitted within the sandbox invocation."
    )
    memory_limit_mb: int = Field(..., description="Sandbox memory ceiling in megabytes.")
    cpu_limit_seconds: int = Field(..., description="Sandbox CPU time limit in seconds.")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Human-readable error message.")
    diagnostics: Optional[SandboxDiagnostics] = None
