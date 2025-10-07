"""Dataclass representations of the symbolic engine proto messages."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Sequence


@dataclass(slots=True)
class SimplifyRequest:
    expression: str = ""
    variables: List[str] = field(default_factory=list)
    canonicalize: bool = True
    method: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "expression": self.expression,
            "variables": list(self.variables),
            "canonicalize": self.canonicalize,
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SimplifyRequest":
        return cls(
            expression=str(payload.get("expression", "")),
            variables=[str(item) for item in payload.get("variables", [])],
            canonicalize=bool(payload.get("canonicalize", True)),
            method=str(payload.get("method", "")),
        )


@dataclass(slots=True)
class DerivativeRequest:
    expression: str = ""
    variables: List[str] = field(default_factory=list)
    variable: str = ""
    order: int = 1
    canonicalize: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "expression": self.expression,
            "variables": list(self.variables),
            "variable": self.variable,
            "order": self.order,
            "canonicalize": self.canonicalize,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "DerivativeRequest":
        return cls(
            expression=str(payload.get("expression", "")),
            variables=[str(item) for item in payload.get("variables", [])],
            variable=str(payload.get("variable", "")),
            order=int(payload.get("order", 1)),
            canonicalize=bool(payload.get("canonicalize", True)),
        )


@dataclass(slots=True)
class IntegralRequest:
    expression: str = ""
    variables: List[str] = field(default_factory=list)
    variable: str = ""
    lower_limit: str | None = None
    upper_limit: str | None = None
    canonicalize: bool = True

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "expression": self.expression,
            "variables": list(self.variables),
            "variable": self.variable,
            "canonicalize": self.canonicalize,
        }
        if self.lower_limit is not None:
            payload["lower_limit"] = self.lower_limit
        if self.upper_limit is not None:
            payload["upper_limit"] = self.upper_limit
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "IntegralRequest":
        lower = payload.get("lower_limit")
        upper = payload.get("upper_limit")
        return cls(
            expression=str(payload.get("expression", "")),
            variables=[str(item) for item in payload.get("variables", [])],
            variable=str(payload.get("variable", "")),
            lower_limit=str(lower) if lower is not None else None,
            upper_limit=str(upper) if upper is not None else None,
            canonicalize=bool(payload.get("canonicalize", True)),
        )


@dataclass(slots=True)
class SolveRequest:
    equation: str = ""
    variable: str = ""
    parameters: List[str] = field(default_factory=list)
    canonicalize: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "equation": self.equation,
            "variable": self.variable,
            "parameters": list(self.parameters),
            "canonicalize": self.canonicalize,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SolveRequest":
        return cls(
            equation=str(payload.get("equation", "")),
            variable=str(payload.get("variable", "")),
            parameters=[str(item) for item in payload.get("parameters", [])],
            canonicalize=bool(payload.get("canonicalize", True)),
        )


@dataclass(slots=True)
class SeriesRequest:
    expression: str = ""
    variables: List[str] = field(default_factory=list)
    variable: str = ""
    point: str = "0"
    order: int = 6
    canonicalize: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "expression": self.expression,
            "variables": list(self.variables),
            "variable": self.variable,
            "point": self.point,
            "order": self.order,
            "canonicalize": self.canonicalize,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SeriesRequest":
        return cls(
            expression=str(payload.get("expression", "")),
            variables=[str(item) for item in payload.get("variables", [])],
            variable=str(payload.get("variable", "")),
            point=str(payload.get("point", "0")),
            order=int(payload.get("order", 6)),
            canonicalize=bool(payload.get("canonicalize", True)),
        )


@dataclass(slots=True)
class CodegenRequest:
    expression: str = ""
    variables: List[str] = field(default_factory=list)
    target: str = "c"
    function_name: str = "symbolic_kernel"
    emit_header: bool = False
    canonicalize: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "expression": self.expression,
            "variables": list(self.variables),
            "target": self.target,
            "function_name": self.function_name,
            "emit_header": self.emit_header,
            "canonicalize": self.canonicalize,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "CodegenRequest":
        return cls(
            expression=str(payload.get("expression", "")),
            variables=[str(item) for item in payload.get("variables", [])],
            target=str(payload.get("target", "c")),
            function_name=str(payload.get("function_name", "symbolic_kernel")),
            emit_header=bool(payload.get("emit_header", False)),
            canonicalize=bool(payload.get("canonicalize", True)),
        )


@dataclass(slots=True)
class SymbolicMetadataEntry:
    key: str
    value: str

    def to_dict(self) -> Dict[str, str]:
        return {"key": self.key, "value": self.value}


@dataclass(slots=True)
class SymbolicResponse:
    result: str = ""
    latex: str | None = None
    canonical_form: str | None = None
    metadata: List[SymbolicMetadataEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {"result": self.result, "metadata": [entry.to_dict() for entry in self.metadata]}
        if self.latex is not None:
            payload["latex"] = self.latex
        if self.canonical_form is not None:
            payload["canonical_form"] = self.canonical_form
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SymbolicResponse":
        entries = [
            SymbolicMetadataEntry(key=str(item.get("key", "")), value=str(item.get("value", "")))
            for item in payload.get("metadata", [])
        ]
        return cls(
            result=str(payload.get("result", "")),
            latex=str(payload["latex"]) if payload.get("latex") is not None else None,
            canonical_form=str(payload["canonical_form"]) if payload.get("canonical_form") is not None else None,
            metadata=entries,
        )


__all__ = [
    "SimplifyRequest",
    "DerivativeRequest",
    "IntegralRequest",
    "SolveRequest",
    "SeriesRequest",
    "CodegenRequest",
    "SymbolicMetadataEntry",
    "SymbolicResponse",
]
