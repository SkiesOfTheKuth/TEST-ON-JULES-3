# Technical Documentation

This document provides a detailed technical overview of the Advanced Calculator project. It is intended for developers who want to understand the project's architecture, codebase, and APIs.

## 1. Project Architecture

The project is designed with a clean separation of concerns, decoupling the user interface from the core business logic. This architecture makes the application modular, scalable, and easy to maintain.

-   **Core Logic (`logic.py`)**: This module is the heart of the application. It contains all the fundamental mathematical functions (`add`, `subtract`, `multiply`, `divide`, `power`, `sqrt`). It is a stateless module with no external dependencies, ensuring that the calculation logic is pure and easily testable.

-   **Expression Evaluator (`asteval`)**: To handle complex, user-provided mathematical expressions safely, the project uses the `asteval` library. `asteval` parses and evaluates strings as Python expressions in a secure, sandboxed environment. Each front-end initializes its own `asteval` interpreter and populates its symbol table with the functions from `logic.py`.

-   **Front-Ends**: The project features three independent front-ends, each serving as a different user interface to the same core logic:
    1.  **Web Application (`app.py`, `templates/`, `static/`)**: A Flask-based web server that provides an interactive calculator in the browser. It communicates with the back-end via an AJAX call to a JSON API endpoint (`/calculate`).
    2.  **GUI Application (`gui_calculator.py`)**: A desktop application built with Python's standard GUI toolkit, Tkinter. It provides a traditional calculator interface that directly calls the `asteval` interpreter.
    3.  **Command-Line Interface (`calculator.py`)**: A simple, text-based interface that runs in the terminal, allowing users to type in expressions and see the results.

-   **Testing (`test_calculator.py`)**: The project's correctness is ensured by a suite of unit tests written with Python's `unittest` framework. These tests target the core functions in `logic.py`, verifying their behavior with a wide range of inputs, including edge cases.

## 2. File-by-File Breakdown

-   **`app.py`**: The entry point for the Flask web application. It defines the routes, including the main page (`/`) and the API endpoint for calculations (`/calculate`). It also initializes the `asteval` interpreter for the web server.

-   **`calculator.py`**: The entry point for the command-line interface (CLI). It contains a loop that reads user input, evaluates it using `asteval`, and prints the result.

-   **`gui_calculator.py`**: The entry point for the Tkinter-based GUI application. It defines the `CalculatorApp` class, which sets up the window, widgets (display, buttons), and event handlers for user interactions.

-   **`logic.py`**: The core logic module. It contains all the standalone mathematical functions. This module has no dependencies on any other part of the application.

-   **`test_calculator.py`**: Contains all the unit tests for the functions in `logic.py`. It uses the `unittest` framework to ensure the mathematical logic is correct.

-   **`templates/index.html`**: The HTML structure for the web calculator interface. It defines the display area and all the buttons.

-   **`static/script.js`**: The client-side JavaScript for the web calculator. It handles button clicks, builds the expression string, and sends it to the Flask back-end for calculation using `fetch`.

-   **`static/style.css`**: The CSS file that styles the web calculator, making it responsive and visually appealing.

## 3. API Reference (`logic.py`)

The following functions are available in the `logic.py` module.

-   `add(x, y)`: Returns the sum of `x` and `y`.
-   `subtract(x, y)`: Returns the result of `x` minus `y`.
-   `multiply(x, y)`: Returns the product of `x` and `y`.
-   `divide(x, y)`: Returns the result of `x` divided by `y`. Raises a `ValueError` if `y` is zero.
-   `power(x, y)`: Returns `x` raised to the power of `y`.
-   `sqrt(x)`: Returns the square root of `x`. Raises a `ValueError` if `x` is negative.

## 4. Web API Endpoint (`/calculate`)

The Flask application exposes a single API endpoint for performing calculations.

-   **Route**: `/calculate`
-   **Method**: `POST`
-   **Request Body (JSON)**:
    ```json
    {
        "expression": "your-expression-string"
    }
    ```
-   **Success Response (200 OK)**:
    ```json
    {
        "result": "the-calculated-result"
    }
    ```
-   **Error Response (400 Bad Request)**:
    If the expression is invalid or missing, the response will be:
    ```json
    {
        "error": "error-message-string"
    }
    ```