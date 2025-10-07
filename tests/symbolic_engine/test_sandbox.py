import pytest

from services.symbolic_engine.app.sandbox import (
    SandboxTimeoutError,
    run_sandbox,
)


def test_trigonometric_identity_simplifies_to_one():
    result = run_sandbox("sin(x)**2 + cos(x)**2")
    assert result["simplified"] == "1"


def test_numeric_substitutions_return_numeric_value():
    result = run_sandbox("x**2 + y", {"x": 2, "y": 3})
    assert result["evaluated"] == pytest.approx(7.0)


def test_timeout_guard_terminates_worker():
    with pytest.raises(SandboxTimeoutError):
        run_sandbox("x + 1", timeout_s=1e-6)
