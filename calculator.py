import asteval
import logic

def main():
    """
    Main function to run the calculator.
    Initializes an asteval interpreter and enters a loop to evaluate user input.
    """
    # Create a new asteval interpreter
    a = asteval.Interpreter()

    # Add the functions from our logic module to the interpreter's symbol table
    a.symtable.update({
        'add': logic.add,
        'subtract': logic.subtract,
        'multiply': logic.multiply,
        'divide': logic.divide,
        'power': logic.power,
        'sqrt': logic.sqrt,
        'sin': logic.sin,
        'cos': logic.cos,
        'tan': logic.tan,
        'log': logic.log,
        'log10': logic.log10,
        'factorial': logic.factorial,
        'percentage': logic.percentage,
    })

    print("Welcome to the advanced calculator!")
    print("You can use functions like: add, subtract, multiply, divide, power, sqrt, sin, cos, tan, log, log10, factorial, percentage")
    print("For example: 'sqrt(16) + 5' or '(2 + 3) * 4'")
    print("Enter 'quit' to exit.")

    while True:
        expression = input("Enter a calculation: ")

        if expression.lower() == 'quit':
            break

        try:
            # Evaluate the expression using the asteval interpreter
            result = a.eval(expression)
            print(f"Result: {result}")

        except Exception as e:
            # Catch potential errors from asteval (e.g., syntax errors, undefined variables)
            print(f"Error: {e}")

if __name__ == "__main__":
    main()