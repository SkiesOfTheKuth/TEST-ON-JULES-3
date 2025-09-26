import pytest
from playwright.sync_api import Page, expect
import subprocess
import time
import os
import signal

# --- Test Setup and Teardown ---

@pytest.fixture(scope="session")
def flask_app():
    """
    Starts the Flask web server as a background process for the test session.
    """
    # Command to run the Flask app
    command = ["python", "app.py"]

    # Start the server as a subprocess
    # Use preexec_fn=os.setsid to create a new process group
    server_process = subprocess.Popen(command, preexec_fn=os.setsid)

    # Wait a moment for the server to start
    time.sleep(2)

    # Yield the process object to the tests
    yield server_process

    # Teardown: Stop the server after tests are done
    # Kill the entire process group to ensure the Flask app is terminated
    os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)

# --- Test Cases ---

def test_calculator_title(page: Page, flask_app):
    """
    Tests that the main page has the correct title.
    """
    page.goto("http://127.0.0.1:5000")
    expect(page).to_have_title("Advanced Web Calculator")

def test_basic_addition(page: Page, flask_app):
    """
    Tests a simple addition operation: 7 + 5 = 12.
    """
    page.goto("http://127.0.0.1:5000")

    # Click buttons for "7 + 5 ="
    page.click("button[data-value='7']")
    page.click("button[data-value='+']")
    page.click("button[data-value='5']")
    page.click("button[data-value='=']")

    # Check that the display shows the result "12"
    display = page.locator("#display")
    expect(display).to_have_value("12")

def test_calculation_with_functions(page: Page, flask_app):
    """
    Tests a more complex calculation involving functions: sqrt(16) + cosd(0) = 5.
    cosd(0) is 1.
    """
    page.goto("http://127.0.0.1:5000")

    # sqrt(16)
    page.click("button[data-value='sqrt(']")
    page.click("button[data-value='1']")
    page.click("button[data-value='6']")
    page.click("button[data-value=')']")

    # +
    page.click("button[data-value='+']")

    # cosd(0)
    page.click("button[data-value='cosd(']")
    page.click("button[data-value='0']")
    page.click("button[data-value=')']")

    # =
    page.click("button[data-value='=']")

    # Check for the result "5"
    display = page.locator("#display")
    expect(display).to_have_value("5")

def test_history_feature(page: Page, flask_app):
    """
    Tests that calculations appear in the history panel.
    """
    page.goto("http://127.0.0.1:5000")

    # Perform a calculation: 9 * 3 = 27
    page.click("button[data-value='9']")
    page.click("button[data-value='*']")
    page.click("button[data-value='3']")
    page.click("button[data-value='=']")

    # Check that the display is correct
    expect(page.locator("#display")).to_have_value("27")

    # Check that the history panel contains the calculation
    history_panel = page.locator("#history-panel")
    expect(history_panel).to_contain_text("9*3 = 27")

    # Perform another calculation: 10 - 2 = 8
    page.click("button[data-value='C']") # Clear
    page.click("button[data-value='1']")
    page.click("button[data-value='0']")
    page.click("button[data-value='-']")
    page.click("button[data-value='2']")
    page.click("button[data-value='=']")

    # Check that the new calculation is at the top of the history
    expect(history_panel).to_contain_text("10-2 = 8")
    expect(history_panel).to_contain_text("9*3 = 27")

def test_memory_functions(page: Page, flask_app):
    """
    Tests the memory functions: M+, MR, and MC.
    """
    page.goto("http://127.0.0.1:5000")

    # 1. Add 10 to memory
    page.click("button[data-value='1']")
    page.click("button[data-value='0']")
    page.click("button[data-value='M+']") # Memory is now 10

    # 2. Clear display and add 5 to memory
    page.click("button[data-value='C']")
    page.click("button[data-value='5']")
    page.click("button[data-value='M+']") # Memory is now 15

    # 3. Recall memory
    page.click("button[data-value='MR']")
    expect(page.locator("#display")).to_have_value("15")

    # 4. Subtract 3 from memory
    page.click("button[data-value='C']")
    page.click("button[data-value='3']")
    page.click("button[data-value='M-']") # Memory is now 12

    # 5. Clear memory and recall
    page.click("button[data-value='MC']")
    page.click("button[data-value='MR']")
    expect(page.locator("#display")).to_have_value("0")