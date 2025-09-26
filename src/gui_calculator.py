import tkinter as tk
from tkinter import font
from .evaluator import create_evaluator

class CalculatorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Advanced Calculator")
        self.geometry("480x550")  # Updated geometry for a 5-column layout
        self.resizable(False, False)

        self.asteval = create_evaluator()

        self.expression = ""
        self.create_widgets()

    def create_widgets(self):
        # --- Display Screen ---
        display_font = font.Font(family='Helvetica', size=28, weight='bold')
        self.display_var = tk.StringVar()
        display = tk.Entry(self, textvariable=self.display_var, font=display_font, bd=10, insertwidth=2, width=14, borderwidth=4, relief="ridge", justify='right', state='readonly')
        display.grid(row=0, column=0, columnspan=5, ipady=10, sticky="nsew")

        # --- Button Frame ---
        button_frame = tk.Frame(self)
        button_frame.grid(row=1, column=0, columnspan=5, sticky="nsew")

        button_font = font.Font(family='Helvetica', size=16)

        buttons = [
            # Row 1
            {'text': 'abs', 'val': 'abs(', 'row': 1, 'col': 0},
            {'text': 'round', 'val': 'round(', 'row': 1, 'col': 1},
            {'text': '(', 'val': '(', 'row': 1, 'col': 2},
            {'text': ')', 'val': ')', 'row': 1, 'col': 3},
            {'text': 'C', 'val': 'C', 'row': 1, 'col': 4},
            # Row 2
            {'text': 'sin', 'val': 'sin(', 'row': 2, 'col': 0},
            {'text': 'cos', 'val': 'cos(', 'row': 2, 'col': 1},
            {'text': 'tan', 'val': 'tan(', 'row': 2, 'col': 2},
            {'text': 'log', 'val': 'log(', 'row': 2, 'col': 3},
            {'text': 'log10', 'val': 'log10(', 'row': 2, 'col': 4},
            # Row 3
            {'text': '7', 'val': '7', 'row': 3, 'col': 0},
            {'text': '8', 'val': '8', 'row': 3, 'col': 1},
            {'text': '9', 'val': '9', 'row': 3, 'col': 2},
            {'text': '÷', 'val': '/', 'row': 3, 'col': 3},
            {'text': '×', 'val': '*', 'row': 3, 'col': 4},
            # Row 4
            {'text': '4', 'val': '4', 'row': 4, 'col': 0},
            {'text': '5', 'val': '5', 'row': 4, 'col': 1},
            {'text': '6', 'val': '6', 'row': 4, 'col': 2},
            {'text': '+', 'val': '+', 'row': 4, 'col': 3},
            {'text': '−', 'val': '-', 'row': 4, 'col': 4},
            # Row 5
            {'text': '1', 'val': '1', 'row': 5, 'col': 0},
            {'text': '2', 'val': '2', 'row': 5, 'col': 1},
            {'text': '3', 'val': '3', 'row': 5, 'col': 2},
            {'text': 'sqrt', 'val': 'sqrt(', 'row': 5, 'col': 3},
            {'text': 'xʸ', 'val': '**', 'row': 5, 'col': 4},
            # Row 6
            {'text': '0', 'val': '0', 'row': 6, 'col': 0},
            {'text': '.', 'val': '.', 'row': 6, 'col': 1},
            {'text': 'π', 'val': 'pi', 'row': 6, 'col': 2},
            {'text': 'e', 'val': 'e', 'row': 6, 'col': 3},
            {'text': '=', 'val': '=', 'row': 6, 'col': 4},
        ]

        color_map = {
            'C': '#dc3545', '=': '#28a745',
            '÷': '#ffc107', '×': '#ffc107', '+': '#ffc107', '−': '#ffc107', 'xʸ': '#ffc107',
            '(': '#6c757d', ')': '#6c757d',
            'default_func': '#5a6268'
        }

        for b in buttons:
            text, val, row, col = b['text'], b['val'], b['row'], b['col']

            command = self.calculate if text == '=' else self.clear if text == 'C' else lambda v=val: self.on_button_click(v)

            is_op = text in ['÷', '×', '+', '−', 'xʸ', '(', ')']
            is_special = text in ['C', '=']
            is_num = text in '0123456789.'

            bg = color_map.get(text, '#f8f9fa' if is_num else color_map['default_func'])
            fg = 'white' if not is_num else 'black'

            btn = tk.Button(button_frame, text=text, font=button_font, command=command, height=2, width=4, relief='flat', bg=bg, fg=fg)
            btn.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)

        for i in range(5):
            self.grid_columnconfigure(i, weight=1)
            button_frame.grid_columnconfigure(i, weight=1)
        for i in range(1, 8):
            button_frame.grid_rowconfigure(i, weight=1)

    def on_button_click(self, char):
        self.expression += str(char)
        self.display_var.set(self.expression)

    def calculate(self):
        try:
            result = self.asteval.eval(self.expression)
            self.display_var.set(str(result))
            self.expression = str(result)
        except Exception:
            self.display_var.set("Error")
            self.expression = ""

    def clear(self):
        self.expression = ""
        self.display_var.set("")

if __name__ == "__main__":
    app = CalculatorApp()
    app.mainloop()