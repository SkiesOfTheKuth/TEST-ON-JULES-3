"""Smoke tests for the Tkinter GUI entry point."""

from __future__ import annotations

import subprocess
import sys


def test_gui_smoke_test_success() -> None:
    result = subprocess.run(
        [sys.executable, "gui_calculator.py", "--smoke-test", "2 + 3"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert float(result.stdout.strip()) == 5.0
    assert result.stderr == ""


def test_gui_smoke_test_validation_error() -> None:
    result = subprocess.run(
        [sys.executable, "gui_calculator.py", "--smoke-test", ""],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Validation error" in result.stderr
