from __future__ import annotations

import argparse
import sys
from typing import Optional

from calculator_app.services.evaluator import (
    ExpressionEvaluationError,
    ExpressionValidationError,
    SafeEvaluator,
)


def evaluate_expression(expression: str, evaluator: Optional[SafeEvaluator] = None) -> float:
    """Evaluate a single expression using the shared evaluator."""

    evaluator = evaluator or SafeEvaluator()
    return evaluator.evaluate(expression)


def run_interactive(evaluator: SafeEvaluator) -> None:
    """Interactive REPL loop for terminal usage."""

    print("Welcome to the advanced calculator!")
    print("You can use functions like: add, subtract, multiply, divide, power, sqrt")
    print("For example: 'sqrt(16) + 5' or '(2 + 3) * 4'")
    print("Enter 'quit' to exit.")

    while True:
        expression = input("Enter a calculation: ")

        if expression.lower() == "quit":
            break

        try:
            result = evaluate_expression(expression, evaluator=evaluator)
        except ExpressionValidationError as exc:
            print(f"Validation error: {exc}")
            continue
        except ExpressionEvaluationError as exc:
            print(f"Evaluation error: {exc}")
            continue
        except Exception as exc:  # pragma: no cover - user feedback guardrail
            print(f"Unexpected error: {exc}")
            continue

        print(f"Result: {result}")


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point that supports both interactive and single-run modes."""

    parser = argparse.ArgumentParser(description="Safe calculator CLI")
    parser.add_argument(
        "--expression",
        help="Evaluate a single expression non-interactively and print the result.",
    )
    args = parser.parse_args(argv)

    evaluator = SafeEvaluator()

    if args.expression is not None:
        try:
            result = evaluate_expression(args.expression, evaluator=evaluator)
        except ExpressionValidationError as exc:
            print(f"Validation error: {exc}", file=sys.stderr)
            return 2
        except ExpressionEvaluationError as exc:
            print(f"Evaluation error: {exc}", file=sys.stderr)
            return 3
        except Exception as exc:  # pragma: no cover - user feedback guardrail
            print(f"Unexpected error: {exc}", file=sys.stderr)
            return 4

        print(result)
        return 0

    run_interactive(evaluator)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
