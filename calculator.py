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
    a.symtable['add'] = logic.add
    a.symtable['subtract'] = logic.subtract
    a.symtable['multiply'] = logic.multiply
    a.symtable['divide'] = logic.divide
    a.symtable['power'] = logic.power
    a.symtable['sqrt'] = logic.sqrt

    print("Welcome to the advanced calculator!")
    print("You can use functions like: add, subtract, multiply, divide, power, sqrt")
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