# Advanced Calculator Project

This project is a feature-rich calculator application available in three different interfaces: a modern web application, a desktop GUI application, and a command-line interface (CLI). It is built with Python and features a robust evaluation engine that supports a wide range of mathematical functions and constants.

## Features

- **Multiple Interfaces**:
  - **Web Calculator**: A responsive, modern web interface built with Flask and vanilla JavaScript.
  - **GUI Calculator**: A desktop application built with Python's Tkinter library.
  - **CLI Calculator**: A simple command-line interface for quick calculations.

- **Extended Mathematical Functions**:
  - Basic arithmetic: `+`, `-`, `*`, `/`
  - Exponents (`**` or `^`) and square roots (`sqrt`)
  - Trigonometric functions (in degrees): `sind`, `cosd`, `tand`
  - Inverse trigonometric functions: `asin`, `acos`, `atan`
  - Hyperbolic functions: `sinh`, `cosh`, `tanh`
  - Logarithms: Natural (`log`) and base-10 (`log10`)
  - Factorials (`factorial`)
  - Mathematical constants: `pi` and `e`

- **Robust Error Handling**: The calculator provides clear error messages for invalid syntax, logical errors (e.g., division by zero), and undefined functions.

- **User-Friendly Design**:
  - The web and GUI interfaces are designed to be intuitive and easy to use.
  - The web calculator includes keyboard support for a faster workflow.

## Project Structure

```
.
├── app.py              # Flask backend for the web calculator
├── calculator.py       # Command-line interface (CLI) calculator
├── gui_calculator.py   # Desktop GUI calculator application
├── logic.py            # Core mathematical functions and logic
├── evaluator.py        # asteval interpreter setup
├── static/             # Static assets for the web app (CSS, JS)
│   ├── style.css
│   └── script.js
├── templates/          # HTML templates for the Flask app
│   └── index.html
├── test_app.py         # Tests for the Flask application
└── test_logic.py       # Unit tests for the core logic
```

## Setup and Installation

To run this project, you'll need Python 3 and the following libraries.

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment** (recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required packages**:
    The project requires `Flask` for the web server and `asteval` for expression evaluation.
    ```bash
    pip install Flask asteval
    ```

## How to Run the Calculators

You can run any of the three calculator interfaces.

### 1. Web Calculator

To start the web server, run:
```bash
python app.py
```
The application will be available at `http://127.0.0.1:5000`. Open this URL in your web browser to use the calculator.

### 2. GUI Calculator

To launch the desktop application, run:
```bash
python gui_calculator.py
```
This will open a window with the calculator interface.

### 3. Command-Line (CLI) Calculator

To use the CLI version, run:
```bash
python calculator.py
```
You can then type mathematical expressions directly into the terminal. Enter `quit` to exit.

## Running Tests

To ensure everything is working correctly, you can run the automated tests:
```bash
python -m unittest discover
```
This command will discover and run all tests in `test_app.py` and `test_logic.py`.