"""Secure expression evaluation utilities for the calculator stack."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
import re
from dataclasses import dataclass
from typing import Iterable

import asteval

from calculator_app import operations


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
    max_runtime_seconds: float = 0.1
    max_result_magnitude: float = 1_000_000_000_000.0

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

    def _build_interpreter(self) -> asteval.Interpreter:
        return asteval.Interpreter(
            symtable={
                "sqrt": operations.sqrt,
                "power": operations.power,
            },
            minimal=True,
            use_numpy=False,
            err_writer=None,
        )

    def _execute(self, expression: str) -> float:
        interpreter = self._build_interpreter()
        interpreter.error = []

        result = interpreter(expression)
        if interpreter.error:
            raise ExpressionEvaluationError("Unable to evaluate expression")

        if not isinstance(result, (int, float)):
            raise ExpressionEvaluationError("Expression did not evaluate to a number")

        return float(result)

    def evaluate(self, expression: str) -> float:
        """Validate and evaluate an arithmetic expression."""

        self.validate(expression)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._execute, expression)
            try:
                result = future.result(timeout=self.max_runtime_seconds)
            except TimeoutError as exc:
                future.cancel()
                raise ExpressionEvaluationError("Expression evaluation timed out") from exc

        if abs(result) > self.max_result_magnitude:
            raise ExpressionEvaluationError("Expression result exceeds allowed magnitude")

        return result

    def health_check(self) -> None:
        """Run a lightweight self-test to ensure the evaluator is operational."""

        try:
            self.evaluate("1 + 1")
        except Exception as exc:  # pragma: no cover - exercised via readiness test
            raise RuntimeError("Evaluator health check failed") from exc

