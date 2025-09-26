from engine import create_evaluator

def main():
    """
    Main function to run the calculator.
    Initializes a centralized evaluator and enters a loop to evaluate user input.
    """
    # Create a centralized evaluator
    evaluator = create_evaluator()

    print("Welcome to the advanced calculator!")
    print("You can use functions like: add, subtract, multiply, divide, power, sqrt, sin, cos, tan, log, log10, factorial, percentage")
    print("For example: 'sqrt(16) + 5' or '(2 + 3) * 4'")
    print("Enter 'quit' to exit.")

    while True:
        expression = input("Enter a calculation: ")

        if expression.lower() == 'quit':
            break

        try:
            # Clear previous errors, as the interpreter is reused
            evaluator.error = []
            result = evaluator.eval(expression)

            # Check if any errors occurred during evaluation
            if evaluator.error:
                # Get the first error and format it
                error_message = evaluator.error[0].get_error()[1]
                print(f"Error: {error_message}")
            else:
                print(f"Result: {result}")

        except Exception as e:
            # Catch other unexpected errors
            print(f"Error: {e}")

if __name__ == "__main__":
    main()