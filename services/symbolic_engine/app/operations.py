"""SymPy-powered symbolic operations for the API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

import sympy as sp
from sympy import Eq
from sympy.printing.latex import latex
from sympy.utilities.codegen import codegen


@dataclass
class OperationResult:
    """Container for symbolic results with metadata."""

    result: str
    latex: str | None
    canonical_form: str | None
    metadata: Dict[str, Any]


def _create_symbols(variables: Sequence[str]) -> Dict[str, sp.Symbol]:
    if not variables:
        return {}
    sym_list = sp.symbols(list(dict.fromkeys(variables)))
    if isinstance(sym_list, tuple):
        return {str(symbol): symbol for symbol in sym_list}
    return {str(sym_list): sym_list}


def _canonical(expr: sp.Expr | Sequence[Any]) -> str:
    if isinstance(expr, (list, tuple)):
        return str([_canonical(item) for item in expr])
    return sp.srepr(sp.simplify(expr))


def simplify_expression(
    expression: str,
    variables: Sequence[str],
    method: str | None = None,
    canonicalize: bool = True,
) -> OperationResult:
    symbol_map = _create_symbols(variables)
    expr = sp.sympify(expression, locals=symbol_map)

    if method == "trigsimp":
        simplified = sp.trigsimp(expr)
    elif method == "powsimp":
        simplified = sp.powsimp(expr)
    elif method == "expand":
        simplified = sp.expand(expr)
    else:
        simplified = sp.simplify(expr)

    result = str(simplified)
    result_latex = latex(simplified)
    canonical_form = _canonical(simplified) if canonicalize else None
    metadata = {
        "free_symbols": sorted(str(symbol) for symbol in simplified.free_symbols),
        "method": method or "simplify",
    }
    return OperationResult(result=result, latex=result_latex, canonical_form=canonical_form, metadata=metadata)


def differentiate_expression(
    expression: str,
    variables: Sequence[str],
    variable: str,
    order: int,
    canonicalize: bool = True,
) -> OperationResult:
    symbol_map = _create_symbols([variable, *variables])
    expr = sp.sympify(expression, locals=symbol_map)
    symbol = symbol_map[variable]
    differentiated = sp.diff(expr, symbol, order)

    result = str(differentiated)
    result_latex = latex(differentiated)
    canonical_form = _canonical(differentiated) if canonicalize else None
    metadata = {
        "free_symbols": sorted(str(symbol) for symbol in differentiated.free_symbols),
        "variable": variable,
        "order": order,
    }
    return OperationResult(result=result, latex=result_latex, canonical_form=canonical_form, metadata=metadata)


def integrate_expression(
    expression: str,
    variables: Sequence[str],
    variable: str,
    lower_limit: str | None,
    upper_limit: str | None,
    canonicalize: bool = True,
) -> OperationResult:
    symbol_map = _create_symbols([variable, *variables])
    expr = sp.sympify(expression, locals=symbol_map)
    symbol = symbol_map[variable]

    if lower_limit is not None and upper_limit is not None:
        lower = sp.sympify(lower_limit, locals=symbol_map)
        upper = sp.sympify(upper_limit, locals=symbol_map)
        integrated = sp.integrate(expr, (symbol, lower, upper))
    else:
        integrated = sp.integrate(expr, symbol)

    result = str(integrated)
    result_latex = latex(integrated)
    canonical_form = _canonical(integrated) if canonicalize else None
    metadata = {
        "free_symbols": sorted(str(symbol) for symbol in integrated.free_symbols),
        "variable": variable,
        "definite": lower_limit is not None and upper_limit is not None,
    }
    if lower_limit is not None:
        metadata["lower_limit"] = lower_limit
    if upper_limit is not None:
        metadata["upper_limit"] = upper_limit
    return OperationResult(result=result, latex=result_latex, canonical_form=canonical_form, metadata=metadata)


def solve_equation(
    equation: str,
    variable: str,
    parameters: Iterable[str],
    canonicalize: bool = True,
) -> OperationResult:
    symbol_map = _create_symbols([variable, *parameters])

    if "=" in equation:
        left, right = equation.split("=", maxsplit=1)
        left_expr = sp.sympify(left, locals=symbol_map)
        right_expr = sp.sympify(right, locals=symbol_map)
        expr = Eq(left_expr, right_expr)
        solutions = sp.solve(expr, symbol_map[variable])
    else:
        expr = sp.sympify(equation, locals=symbol_map)
        solutions = sp.solve(expr, symbol_map[variable])

    canonical_form = _canonical(solutions) if canonicalize else None
    metadata = {
        "solution_count": len(solutions),
        "variable": variable,
    }
    result = str(solutions)
    result_latex = latex(sp.Tuple(*solutions)) if solutions else None
    return OperationResult(result=result, latex=result_latex, canonical_form=canonical_form, metadata=metadata)


def series_expansion(
    expression: str,
    variables: Sequence[str],
    variable: str,
    point: str,
    order: int,
    canonicalize: bool = True,
) -> OperationResult:
    symbol_map = _create_symbols([variable, *variables])
    expr = sp.sympify(expression, locals=symbol_map)
    symbol = symbol_map[variable]
    expansion_point = sp.sympify(point, locals=symbol_map)
    series_obj = sp.series(expr, symbol, expansion_point, order)

    result = str(series_obj)
    result_latex = latex(series_obj.removeO())
    canonical_form = _canonical(series_obj.removeO()) if canonicalize else None
    metadata = {
        "variable": variable,
        "point": str(expansion_point),
        "order": order,
    }
    return OperationResult(result=result, latex=result_latex, canonical_form=canonical_form, metadata=metadata)


def generate_code(
    expression: str,
    variables: Sequence[str],
    target: str,
    function_name: str,
    emit_header: bool,
    canonicalize: bool = True,
) -> OperationResult:
    symbol_map = _create_symbols(variables)
    expr = sp.sympify(expression, locals=symbol_map)

    codegen_name = function_name or "symbolic_kernel"
    code_artifacts = codegen((codegen_name, expr), language=target, header=emit_header)

    artifact_map: List[Dict[str, str]] = []
    for artifact_name, artifact_content in code_artifacts:
        artifact_map.append({"name": artifact_name, "content": artifact_content})

    canonical_form = _canonical(expr) if canonicalize else None
    metadata = {
        "target": target,
        "function_name": codegen_name,
        "artifacts": artifact_map,
        "numba_ready": target in {"c", "llvm"},
    }

    result_latex = latex(expr)
    return OperationResult(result=str(expr), latex=result_latex, canonical_form=canonical_form, metadata=metadata)
