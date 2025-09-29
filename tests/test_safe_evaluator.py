"""Tests for the SafeEvaluator sandbox."""

from __future__ import annotations

import pytest

from safe_evaluator import (
    ExpressionEvaluationError,
    ExpressionValidationError,
    SafeEvaluator,
)


def test_evaluate_valid_expression(evaluator: SafeEvaluator) -> None:
    assert evaluator.evaluate("1 + 2 * 3") == pytest.approx(7.0)


def test_validate_rejects_empty_expression(evaluator: SafeEvaluator) -> None:
    with pytest.raises(ExpressionValidationError):
        evaluator.evaluate("   ")


def test_validate_rejects_disallowed_function(evaluator: SafeEvaluator) -> None:
    with pytest.raises(ExpressionValidationError):
        evaluator.evaluate("__import__('os').system('echo hello')")


def test_validate_rejects_long_expression(evaluator: SafeEvaluator) -> None:
    payload = "1+" * 200
    with pytest.raises(ExpressionValidationError):
        evaluator.evaluate(payload)


def test_evaluate_errors_on_invalid_math(evaluator: SafeEvaluator) -> None:
    with pytest.raises(ExpressionEvaluationError):
        evaluator.evaluate("sqrt(-1)")

