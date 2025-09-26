# Advanced Calculator Project

This project is a comprehensive calculator application built with Python, featuring three distinct user interfaces: a web application, a desktop GUI, and a command-line interface (CLI). All three front-ends are powered by a shared core logic module, ensuring consistent and accurate calculations across the different platforms.

## Key Features

- **Multiple Interfaces**: Choose the interface that best suits your needs:
  - **Web Calculator**: A modern, responsive web interface built with Flask and JavaScript.
  - **GUI Calculator**: A classic desktop calculator experience created with Python's Tkinter library.
  - **CLI Calculator**: A straightforward command-line interface for quick calculations.
- **Core Logic Module**: A centralized `logic.py` file containing all the mathematical functions, ensuring that calculations are consistent and easy to maintain.
- **Advanced Operations**: Supports standard arithmetic operations as well as more advanced functions like `power` and `square root`.
- **Expression Evaluation**: Utilizes the `asteval` library to safely evaluate complex mathematical expressions.
- **Comprehensive Test Suite**: Includes a full suite of unit tests to verify the correctness of the calculation logic.

## Getting Started

Follow these instructions to set up the project and get the calculator running on your local machine.

### Prerequisites

- Python 3.6 or higher
- `pip` (Python package installer)

### Installation

1.  **Clone the repository** (or download the source code):
    ```bash
    git clone https://github.com/your-username/advanced-calculator.git
    cd advanced-calculator
    ```

2.  **Install the required Python packages**:
    The project relies on `Flask` for the web application and `asteval` for expression evaluation.
    ```bash
    pip install Flask asteval
    ```

## How to Run the Calculator

You can run any of the three available calculator interfaces.

### 1. Web Calculator

The web calculator is a Flask application.

1.  **Start the Flask development server**:
    ```bash
    python app.py
    ```

2.  **Open your web browser** and navigate to:
    [http://127.0.0.1:5000](http://127.0.0.1:5000)

    You should see the web-based calculator interface, where you can click buttons or type to enter expressions.

### 2. GUI Calculator

The GUI calculator is built with Tkinter.

1.  **Run the GUI script**:
    ```bash
    python gui_calculator.py
    ```

    A desktop window will open with the calculator application.

### 3. Command-Line (CLI) Calculator

The CLI calculator runs directly in your terminal.

1.  **Run the CLI script**:
    ```bash
    python calculator.py
    ```

2.  **Enter mathematical expressions** at the prompt and press `Enter`.
    -   Example: `(15 + 5) * 2`
    -   To exit, type `quit`.

## How to Run the Tests

The project includes a suite of unit tests for the core logic module to ensure everything is working correctly.

1.  **Navigate to the project's root directory**.

2.  **Run the test suite** using Python's built-in `unittest` module:
    ```bash
    python -m unittest test_calculator.py
    ```

    The tests will run, and you will see a confirmation that all tests passed.