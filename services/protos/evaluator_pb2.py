"""Lightweight protobuf replacement for offline testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass(slots=True)
class EvaluateRequest:
    expression: str = ""
    context: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {"expression": self.expression, "context": dict(self.context)}

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "EvaluateRequest":
        return cls(
            expression=str(payload.get("expression", "")),
            context={str(k): str(v) for k, v in dict(payload.get("context", {})).items()},
        )


@dataclass(slots=True)
class EvaluateResponse:
    value: Optional[float] = None
    error: Optional[str] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {"duration_ms": self.duration_ms}
        if self.value is not None:
            payload["value"] = self.value
        if self.error is not None:
            payload["error"] = self.error
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "EvaluateResponse":
        value = payload.get("value")
        error = payload.get("error")
        return cls(
            value=float(value) if value is not None else None,
            error=str(error) if error is not None else None,
            duration_ms=float(payload.get("duration_ms", 0.0)),
        )

    def WhichOneof(self, group: str) -> Optional[str]:
        """Mirror the protobuf API for gateway compatibility."""

        if group != "result":
            return None
        if self.value is not None:
            return "value"
        if self.error is not None:
            return "error"
        return None

    @property
    def result(self) -> str:
        if self.value is not None:
            return "value"
        if self.error is not None:
            return "error"
        return ""


__all__ = ["EvaluateRequest", "EvaluateResponse"]
