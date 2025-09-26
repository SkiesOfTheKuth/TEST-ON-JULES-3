# Advanced Calculator Project

This project is a multi-interface calculator application that provides a web-based UI, a command-line interface (CLI), and a graphical user interface (GUI). It supports a wide range of mathematical operations, from basic arithmetic to scientific functions.

## Features

- **Multiple Interfaces**:
  - **Web Calculator**: A modern, user-friendly web interface built with Flask.
  - **Command-Line Calculator**: An interactive CLI for quick calculations.
  - **GUI Calculator**: A desktop application built with Tkinter.
- **Scientific Functions**:
  - Basic arithmetic: `+`, `-`, `*`, `/`
  - Power and square root: `power()`, `sqrt()`
  - Trigonometric functions: `sin()`, `cos()`, `tan()` (input in degrees)
  - Logarithmic functions: `log()` (natural), `log10()` (base-10)
  - Factorial: `factorial()`
  - Percentage: `percentage()`

## Project Structure

```
.
├── app.py                  # Flask web application
├── calculator.py           # Command-line interface
├── gui_calculator.py       # GUI application
├── logic.py                # Core mathematical functions
├── test_calculator.py      # Unit tests for logic.py
├── test_app.py             # Functional tests for the Flask app
├── templates/
│   └── index.html          # HTML for the web interface
├── static/
│   ├── style.css           # CSS for the web interface
│   └── script.js           # JavaScript for the web interface
├── requirements.txt        # Project dependencies
└── README.md               # This file
```

## Setup and Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Create a virtual environment** (recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## How to Run

### Web Calculator

To start the Flask development server:
```bash
flask run
# or
python3 app.py
```
Open your web browser and navigate to `http://127.0.0.1:5000`.

### Command-Line Calculator

To run the interactive command-line calculator:
```bash
python3 calculator.py
```

### GUI Calculator

To launch the desktop GUI application:
```bash
python3 gui_calculator.py
```

## How to Run Tests

To run all the tests for the project, use the `run_tests.py` script:
```bash
python3 run_tests.py
```
This will automatically discover and run all tests, confirming that the logic and application endpoints are working correctly.