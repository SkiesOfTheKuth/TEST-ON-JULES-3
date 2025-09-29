"""Secure expression evaluation utilities for the calculator stack."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

import asteval

import logic


_ALLOWED_FUNCTIONS: frozenset[str] = frozenset({"sqrt", "power"})
_ALLOWED_CHARS: frozenset[str] = frozenset(
    "0123456789+-*/()., " + "".join(sorted(_ALLOWED_FUNCTIONS))
)


class ExpressionValidationError(ValueError):
    """Raised when a candidate expression fails validation rules."""


class ExpressionEvaluationError(RuntimeError):
    """Raised when the evaluator cannot successfully compute a result."""


@dataclass(slots=True)
class SafeEvaluator:
    """A thin sandbox around :mod:`asteval` with strict validation."""

    max_expression_length: int = 256
    _interpreter: asteval.Interpreter = field(init=False, repr=False)

    def __post_init__(self) -> None:  # pragma: no cover - deterministic configuration
        object.__setattr__(
            self,
            "_interpreter",
            asteval.Interpreter(
                symtable={
                    "sqrt": logic.sqrt,
                    "power": logic.power,
                },
                minimal=True,
                use_numpy=False,
                err_writer=None,
            ),
        )

    def _validate_length(self, expression: str) -> None:
        if len(expression) > self.max_expression_length:
            raise ExpressionValidationError("Expression exceeds maximum length")

    def _validate_characters(self, expression: str) -> None:
        invalid_chars = set(expression) - _ALLOWED_CHARS
        if invalid_chars:
            raise ExpressionValidationError(
                f"Expression contains unsupported characters: {sorted(invalid_chars)!r}"
            )

    def _validate_tokens(self, expression: str) -> None:
        tokens: Iterable[str] = re.findall(r"[A-Za-z_]+", expression)
        disallowed = [token for token in tokens if token not in _ALLOWED_FUNCTIONS]
        if disallowed:
            raise ExpressionValidationError(
                f"Expression contains unsupported functions: {sorted(set(disallowed))!r}"
            )

    def validate(self, expression: str) -> None:
        """Run all validation checks on ``expression``."""

        candidate = expression.strip()
        if not candidate:
            raise ExpressionValidationError("Expression cannot be empty")

        self._validate_length(candidate)
        self._validate_characters(candidate)
        self._validate_tokens(candidate)

    def evaluate(self, expression: str) -> float:
        """Validate and evaluate an arithmetic expression."""

        self.validate(expression)

        self._interpreter.symtable["sqrt"] = logic.sqrt
        self._interpreter.symtable["power"] = logic.power
        self._interpreter.error = []

        result = self._interpreter(expression)
        if self._interpreter.error:
            raise ExpressionEvaluationError("Unable to evaluate expression")

        if not isinstance(result, (int, float)):
            raise ExpressionEvaluationError("Expression did not evaluate to a number")

        return float(result)

