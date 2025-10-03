"""Smoke tests for the CLI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_cli_expression_success() -> None:
    result = subprocess.run(
        [sys.executable, "calculator.py", "--expression", "1 + 2"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert float(result.stdout.strip()) == pytest.approx(3.0)
    assert result.stderr == ""


def test_cli_expression_validation_error() -> None:
    result = subprocess.run(
        [sys.executable, "calculator.py", "--expression", ""],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "Validation error" in result.stderr
