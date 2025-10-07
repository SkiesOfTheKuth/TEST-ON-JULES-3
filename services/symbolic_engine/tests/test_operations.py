import sympy as sp

from app.models import CodegenOptions, ExpressionContext, SymbolicOperation
from app.operations import SymbolicExecutionError, execute_symbolic_operation


def test_simplify_basic_expression():
    result = execute_symbolic_operation(
        SymbolicOperation.SIMPLIFY,
        "x**2 + 2*x + 1",
        ExpressionContext(),
        variable=None,
        order=None,
        codegen=CodegenOptions(targets=["python"]),
    )
    assert result.canonical == "(x + 1)**2"
    assert any(token in result.code["python"] for token in ("pow", "**"))


def test_derivative_with_variable():
    result = execute_symbolic_operation(
        SymbolicOperation.DERIVATIVE,
        "sin(x)",
        ExpressionContext(),
        variable="x",
        order=None,
        codegen=CodegenOptions(),
    )
    assert result.canonical == "cos(x)"
    assert result.approx_value is None


def test_integral_defaults_to_x():
    context = ExpressionContext()
    result = execute_symbolic_operation(
        SymbolicOperation.INTEGRAL,
        "2*x",
        context,
        variable=None,
        order=None,
        codegen=CodegenOptions(),
    )
    assert result.canonical == "x**2"


def test_solve_returns_finite_set():
    result = execute_symbolic_operation(
        SymbolicOperation.SOLVE,
        "x**2 - 4",
        ExpressionContext(),
        variable="x",
        order=None,
        codegen=CodegenOptions(),
    )
    assert result.canonical in {"{-2, 2}", "{2, -2}"}


def test_series_produces_terms():
    res = execute_symbolic_operation(
        SymbolicOperation.SERIES,
        "exp(x)",
        ExpressionContext(),
        variable="x",
        order=5,
        codegen=CodegenOptions(),
    )
    assert res.series_terms is not None
    assert "x**2/2" in res.series_terms


def test_codegen_explicit_targets():
    res = execute_symbolic_operation(
        SymbolicOperation.CODEGEN,
        "sin(x) + cos(x)",
        ExpressionContext(),
        variable="x",
        order=None,
        codegen=CodegenOptions(targets=["c", "python"]),
    )
    assert "cc" not in res.code  # ensure normalization
    assert "c" in res.code and "python" in res.code


def test_expression_parse_failure():
    context = ExpressionContext()
    try:
        execute_symbolic_operation(
            SymbolicOperation.SIMPLIFY,
            "import os",
            context,
            variable=None,
            order=None,
            codegen=CodegenOptions(),
        )
    except SymbolicExecutionError as exc:
        assert "Failed to parse expression" in str(exc)
    else:
        raise AssertionError("Expected SymbolicExecutionError")
