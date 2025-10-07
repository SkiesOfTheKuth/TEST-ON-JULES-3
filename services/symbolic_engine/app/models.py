from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SymbolicOperation(str, Enum):
    SIMPLIFY = "simplify"
    DERIVATIVE = "derivative"
    INTEGRAL = "integral"
    SOLVE = "solve"
    SERIES = "series"
    CODEGEN = "codegen"


class ExpressionContext(BaseModel):
    variables: Dict[str, float | int | str] = Field(default_factory=dict)
    parameters: Dict[str, float | int | str] = Field(default_factory=dict)


class CodegenOptions(BaseModel):
    targets: List[str] = Field(default_factory=lambda: ["python"])
    human_readable: bool = True


class SymbolicComputeRequest(BaseModel):
    operation: SymbolicOperation
    expression: str
    variable: Optional[str] = None
    order: Optional[int] = None
    context: ExpressionContext = Field(default_factory=ExpressionContext)
    codegen: CodegenOptions = Field(default_factory=CodegenOptions)


class SymbolicResult(BaseModel):
    canonical: str
    latex: str
    approx_value: Optional[float] = None
    code: Dict[str, str] = Field(default_factory=dict)
    series_terms: Optional[List[str]] = None


class SymbolicMetadata(BaseModel):
    execution_ms: float
    used_numba: bool = False
    warnings: List[str] = Field(default_factory=list)


class SymbolicComputeResponse(BaseModel):
    result: SymbolicResult
    metadata: SymbolicMetadata
