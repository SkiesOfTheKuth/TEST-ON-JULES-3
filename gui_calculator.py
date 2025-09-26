import tkinter as tk
from tkinter import font
from evaluator import create_evaluator

class ModernCalculatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Modern Calculator")
        self.geometry("480x640")
        self.configure(bg="#f0f2f5")

        self.expression = "0"
        self.create_widgets()
        self.bind_keyboard_events()

    def create_widgets(self):
        # --- Font Configuration ---
        display_font = font.Font(family='Segoe UI', size=36, weight='bold')
        button_font = font.Font(family='Segoe UI', size=14)
        function_font = font.Font(family='Segoe UI', size=12)

        # --- Display Screen ---
        self.display_var = tk.StringVar(value=self.expression)
        display_entry = tk.Entry(
            self, textvariable=self.display_var, font=display_font,
            bg="#222a37", fg="#ffffff", bd=0, relief="flat", justify='right',
            insertbackground="#ffffff"
        )
        display_entry.grid(row=0, column=0, columnspan=5, sticky="nsew", padx=10, pady=20, ipady=10)
        display_entry.focus()

        # --- Button Definitions ---
        buttons = [
            # Row 1: Functions
            {'text': 'sin', 'value': 'sind(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': 'cos', 'value': 'cosd(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': 'tan', 'value': 'tand(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': 'ln', 'value': 'log(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': '√', 'value': 'sqrt(', 'font': button_font, 'bg': '#e9ecef'},

            # Row 2: Functions
            {'text': 'asin', 'value': 'asin(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': 'acos', 'value': 'acos(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': 'atan', 'value': 'atan(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': 'log10', 'value': 'log10(', 'font': function_font, 'bg': '#e9ecef'},
            {'text': 'n!', 'value': 'factorial(', 'font': button_font, 'bg': '#e9ecef'},

            # Row 3: Constants & Operators
            {'text': 'π', 'value': 'pi', 'font': button_font, 'bg': '#ffc107', 'fg': '#fff'},
            {'text': 'e', 'value': 'e', 'font': button_font, 'bg': '#ffc107', 'fg': '#fff'},
            {'text': '(', 'value': '(', 'font': button_font, 'bg': '#e9ecef'},
            {'text': ')', 'value': ')', 'font': button_font, 'bg': '#e9ecef'},
            {'text': '^', 'value': '**', 'font': button_font, 'bg': '#ffc107', 'fg': '#fff'},

            # Row 4: Numpad
            {'text': '7', 'value': '7', 'font': button_font},
            {'text': '8', 'value': '8', 'font': button_font},
            {'text': '9', 'value': '9', 'font': button_font},
            {'text': '÷', 'value': '/', 'font': button_font, 'bg': '#ffc107', 'fg': '#fff'},
            {'text': 'C', 'value': 'C', 'font': button_font, 'bg': '#dc3545', 'fg': '#fff'},

            # Row 5: Numpad
            {'text': '4', 'value': '4', 'font': button_font},
            {'text': '5', 'value': '5', 'font': button_font},
            {'text': '6', 'value': '6', 'font': button_font},
            {'text': '×', 'value': '*', 'font': button_font, 'bg': '#ffc107', 'fg': '#fff'},
            {'text': '⌫', 'value': 'Backspace', 'font': button_font, 'bg': '#6c757d', 'fg': '#fff'},

            # Row 6 & 7: Numpad
            {'text': '1', 'value': '1', 'font': button_font},
            {'text': '2', 'value': '2', 'font': button_font},
            {'text': '3', 'value': '3', 'font': button_font},
            {'text': '-', 'value': '-', 'font': button_font, 'bg': '#ffc107', 'fg': '#fff'},
            {'text': '=', 'value': '=', 'font': button_font, 'bg': '#28a745', 'fg': '#fff', 'rowspan': 2},

            {'text': '0', 'value': '0', 'font': button_font, 'colspan': 2},
            {'text': '.', 'value': '.', 'font': button_font},
            {'text': '+', 'value': '+', 'font': button_font, 'bg': '#ffc107', 'fg': '#fff'},
        ]

        # --- Grid Layout ---
        row, col = 1, 0
        for config in buttons:
            btn = tk.Button(
                self, text=config['text'], font=config['font'],
                bg=config.get('bg', '#f8f9fa'), fg=config.get('fg', '#000'),
                bd=0, relief="flat",
                command=lambda v=config['value']: self.on_press(v)
            )
            rowspan = config.get('rowspan', 1)
            colspan = config.get('colspan', 1)
            btn.grid(row=row, column=col, rowspan=rowspan, columnspan=colspan, sticky="nsew", padx=2, pady=2)

            col += colspan
            if col >= 5:
                col = 0
                row += 1

        # --- Grid Configuration ---
        self.grid_rowconfigure(0, weight=2)
        for i in range(1, 8):
            self.grid_rowconfigure(i, weight=1)
        for i in range(5):
            self.grid_columnconfigure(i, weight=1)

    def on_press(self, value):
        if value == 'C':
            self.expression = "0"
        elif value == 'Backspace':
            self.expression = self.expression[:-1] if len(self.expression) > 1 else "0"
        elif value == '=':
            self.calculate()
        else:
            if self.expression == "0":
                self.expression = value
            else:
                self.expression += value
        self.display_var.set(self.expression)

    def calculate(self):
        evaluator = create_evaluator()
        try:
            result = evaluator.eval(self.expression)
            if evaluator.error:
                error_message = evaluator.error[0].get_error()[1]
                self.display_var.set(error_message)
            else:
                self.display_var.set(str(result))
                self.expression = str(result)
        except Exception as e:
            self.display_var.set(str(e))
            self.expression = ""

    def bind_keyboard_events(self):
        self.bind('<Return>', lambda event: self.on_press('='))
        self.bind('<BackSpace>', lambda event: self.on_press('Backspace'))
        self.bind('c', lambda event: self.on_press('C'))

        for char in "0123456789.+-*/()":
            self.bind(char, lambda event, c=char: self.on_press(c))

if __name__ == "__main__":
    app = ModernCalculatorApp()
    app.mainloop()