from evaluator import create_evaluator

def main():
    """
    Main function to run the calculator.
    Initializes an asteval interpreter and enters a loop to evaluate user input.
    """
    # Create a new asteval interpreter
    a = create_evaluator()

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