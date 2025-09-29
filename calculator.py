from __future__ import annotations

from safe_evaluator import (
    ExpressionEvaluationError,
    ExpressionValidationError,
    SafeEvaluator,
)

def main():
    """
    Main function to run the calculator.
    Initializes an asteval interpreter and enters a loop to evaluate user input.
    """
    evaluator = SafeEvaluator()

    print("Welcome to the advanced calculator!")
    print("You can use functions like: add, subtract, multiply, divide, power, sqrt")
    print("For example: 'sqrt(16) + 5' or '(2 + 3) * 4'")
    print("Enter 'quit' to exit.")

    while True:
        expression = input("Enter a calculation: ")

        if expression.lower() == 'quit':
            break

        try:
            result = evaluator.evaluate(expression)
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


if __name__ == "__main__":
    main()
