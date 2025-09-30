import argparse
import sys
import tkinter as tk
from tkinter import font

from calculator_app.services.evaluator import (
    ExpressionEvaluationError,
    ExpressionValidationError,
    SafeEvaluator,
)

class CalculatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Calculator")
        self.geometry("400x600")
        self.resizable(False, False)

        self.evaluator = SafeEvaluator()

        self.expression = ""
        self.create_widgets()

    def create_widgets(self):
        # --- Display Screen ---
        display_font = font.Font(family='Helvetica', size=28, weight='bold')
        self.display_var = tk.StringVar()
        display = tk.Entry(self, textvariable=self.display_var, font=display_font, bd=10, insertwidth=2, width=14, borderwidth=4, relief="ridge", justify='right')
        display.grid(row=0, column=0, columnspan=4, ipady=10, sticky="nsew")

        # --- Button Frame ---
        button_frame = tk.Frame(self)
        button_frame.grid(row=1, column=0, columnspan=4, sticky="nsew")

        button_font = font.Font(family='Helvetica', size=18)

        buttons = [
            ('7', 1, 0), ('8', 1, 1), ('9', 1, 2), ('/', 1, 3),
            ('4', 2, 0), ('5', 2, 1), ('6', 2, 2), ('*', 2, 3),
            ('1', 3, 0), ('2', 3, 1), ('3', 3, 2), ('-', 3, 3),
            ('0', 4, 0), ('.', 4, 1), ('+', 4, 2), ('=', 4, 3),
            ('C', 5, 0), ('(', 5, 1), (')', 5, 2), ('power(', 5, 3),
            ('sqrt(', 6, 0, 2)  # span 2 columns
        ]

        for (text, row, col, *span) in buttons:
            colspan = span[0] if span else 1
            if text == '=':
                btn = tk.Button(button_frame, text=text, font=button_font, command=self.calculate, height=2, width=5, bg="#c8e6c9")
            elif text == 'C':
                btn = tk.Button(button_frame, text=text, font=button_font, command=self.clear, height=2, width=5, bg="#ffcdd2")
            else:
                # Use a lambda to capture the current button text
                btn = tk.Button(button_frame, text=text, font=button_font, command=lambda t=text: self.on_button_click(t), height=2, width=5)

            btn.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=1, pady=1)

        # Configure grid weights for proper scaling
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=5)
        for i in range(4):
            self.grid_columnconfigure(i, weight=1)

        for i in range(7):
            button_frame.grid_rowconfigure(i, weight=1)
        for i in range(4):
            button_frame.grid_columnconfigure(i, weight=1)

    def on_button_click(self, char):
        """Append the character from the button to the expression string."""
        self.expression += str(char)
        self.display_var.set(self.expression)

    def calculate(self):
        """Evaluate the expression in the display."""
        try:
            result = self.evaluator.evaluate(self.expression)
        except ExpressionValidationError as exc:
            self.display_var.set("Validation error")
            self.expression = ""
            return
        except ExpressionEvaluationError:
            self.display_var.set("Invalid expression")
            self.expression = ""
            return
        except Exception:
            self.display_var.set("Error")
            self.expression = ""
            return

        self.display_var.set(str(result))
        self.expression = str(result)

    def clear(self):
        """Clear the display and the expression."""
        self.expression = ""
        self.display_var.set("")

def smoke_test(expression: str) -> float:
    """Evaluate an expression without launching the GUI."""

    evaluator = SafeEvaluator()
    return evaluator.evaluate(expression)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Tkinter calculator application")
    parser.add_argument(
        "--smoke-test",
        help="Evaluate an expression and exit without starting the GUI.",
    )
    args = parser.parse_args(argv)

    if args.smoke_test is not None:
        try:
            result = smoke_test(args.smoke_test)
        except ExpressionValidationError as exc:
            print(f"Validation error: {exc}", file=sys.stderr)
            return 2
        except ExpressionEvaluationError as exc:
            print(f"Evaluation error: {exc}", file=sys.stderr)
            return 3
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"Unexpected error: {exc}", file=sys.stderr)
            return 4

        print(result)
        return 0

    app = CalculatorApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
