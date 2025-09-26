import tkinter as tk
from tkinter import font
from engine import create_evaluator

class CalculatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Calculator")
        self.geometry("500x700")
        self.resizable(True, True)

        self.evaluator = create_evaluator()

        self.expression = ""
        self.create_widgets()

    def create_widgets(self):
        # --- Display Screen ---
        display_font = font.Font(family='Helvetica', size=36, weight='bold')
        self.display_var = tk.StringVar()
        display = tk.Entry(self, textvariable=self.display_var, font=display_font, bd=10, insertwidth=2, width=14, borderwidth=4, relief="ridge", justify='right')
        display.grid(row=0, column=0, columnspan=5, ipady=20, sticky="nsew")

        # --- Button Frame ---
        button_frame = tk.Frame(self, bg="#f0f0f0")
        button_frame.grid(row=1, column=0, columnspan=5, sticky="nsew")

        button_font = font.Font(family='Helvetica', size=16)

        buttons = [
            ('sin', 1, 0, '#6c757d'), ('cos', 1, 1, '#6c757d'), ('tan', 1, 2, '#6c757d'), ('log', 1, 3, '#6c757d'), ('log10', 1, 4, '#6c757d'),
            ('sqrt', 2, 0, '#6c757d'), ('x!', 2, 1, '#6c757d'), ('xʸ', 2, 2, '#6c757d'), ('%', 2, 3, '#6c757d'), ('C', 2, 4, '#dc3545'),
            ('7', 3, 0), ('8', 3, 1), ('9', 3, 2), ('/', 3, 3, '#f59e0b'), ('*', 3, 4, '#f59e0b'),
            ('4', 4, 0), ('5', 4, 1), ('6', 4, 2), ('-', 4, 3, '#f59e0b'), ('+', 4, 4, '#f59e0b'),
            ('1', 5, 0), ('2', 5, 1), ('3', 5, 2), ('(', 5, 3), (')', 5, 4),
            ('0', 6, 0, None, 2), ('.', 6, 2), ('=', 6, 3, '#28a745', 2)
        ]

        for (text, row, col, *args) in buttons:
            bg_color = args[0] if args and args[0] else "#e0e0e0"
            colspan = args[1] if len(args) > 1 and args[1] else 1

            action = self.on_button_click
            if text == 'C':
                action = self.clear
            elif text == '=':
                action = self.calculate

            # Map button text to function calls
            func_map = {
                'sin': 'sin(', 'cos': 'cos(', 'tan': 'tan(', 'log': 'log(', 'log10': 'log10(',
                'sqrt': 'sqrt(', 'x!': 'factorial(', 'xʸ': 'power(',' %': 'percentage('
            }

            button_val = func_map.get(text, text)

            btn = tk.Button(button_frame, text=text, font=button_font, bg=bg_color, fg='white' if bg_color != '#e0e0e0' else 'black',
                           command=lambda v=button_val, t=text: action(v) if t in ['C', '='] else self.on_button_click(v),
                           height=2, relief='flat', overrelief='ridge')
            btn.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=2, pady=2)


        # Configure grid weights for proper scaling
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=5)
        for i in range(5):
            self.grid_columnconfigure(i, weight=1)

        for i in range(7):
            button_frame.grid_rowconfigure(i, weight=1)
        for i in range(5):
            button_frame.grid_columnconfigure(i, weight=1)

    def on_button_click(self, char):
        """Append the character from the button to the expression string."""
        self.expression += str(char)
        self.display_var.set(self.expression)

    def calculate(self, *args):
        """Evaluate the expression in the display."""
        try:
            # Clear previous errors, as the interpreter is reused
            self.evaluator.error = []
            result = self.evaluator.eval(self.expression)

            # Check if any errors occurred during evaluation
            if self.evaluator.error:
                self.display_var.set("Error")
                self.expression = ""
            else:
                # Format result to avoid long decimals
                formatted_result = f"{result:.10f}".rstrip('0').rstrip('.')
                self.display_var.set(formatted_result)
                self.expression = str(formatted_result)
        except Exception as e:
            self.display_var.set("Error")
            self.expression = ""

    def clear(self, *args):
        """Clear the display and the expression."""
        self.expression = ""
        self.display_var.set("0")

if __name__ == "__main__":
    app = CalculatorApp()
    app.mainloop()