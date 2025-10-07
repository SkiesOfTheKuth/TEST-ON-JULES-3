import sympy as sp

from services.symbolic_engine.app import operations


def test_simplify_expression_polynomial():
    result = operations.simplify_expression("x**2 + 2*x + 1", ["x"], canonicalize=True)
    assert sp.simplify(result.result) == sp.simplify("x**2 + 2*x + 1")
    assert "free_symbols" in result.metadata
    assert result.canonical_form is not None


def test_derivative_expression_basic():
    result = operations.differentiate_expression("sin(x)", ["x"], variable="x", order=1)
    assert result.result == "cos(x)"
    assert result.metadata["order"] == 1


def test_integral_expression_definite():
    result = operations.integrate_expression(
        "x",
        ["x"],
        variable="x",
        lower_limit="0",
        upper_limit="2",
        canonicalize=True,
    )
    assert result.result == "2"
    assert result.metadata["definite"] is True


def test_solve_equation_linear():
    result = operations.solve_equation("x - 4", variable="x", parameters=[], canonicalize=True)
    assert "4" in result.result
    assert result.metadata["solution_count"] == 1


def test_series_expansion():
    result = operations.series_expansion("sin(x)", ["x"], variable="x", point="0", order=4)
    assert "x - x**3/6" in result.result
    assert result.metadata["order"] == 4


def test_codegen_generates_artifacts():
    result = operations.generate_code("x + y", ["x", "y"], target="c", function_name="f", emit_header=False)
    assert result.metadata["target"] == "c"
    assert any("content" in artifact for artifact in result.metadata["artifacts"])
