from __future__ import annotations

from typing import Dict, Iterable, Tuple

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from .models import CodegenOptions, ExpressionContext, SymbolicOperation, SymbolicResult

_TRANSFORMATIONS = (
    standard_transformations + (implicit_multiplication_application, convert_xor)
)

_ALLOWED_FUNCTIONS: Dict[str, object] = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "exp": sp.exp,
    "log": sp.log,
    "sqrt": sp.sqrt,
    "abs": sp.Abs,
    "ceiling": sp.ceiling,
    "floor": sp.floor,
    "max": sp.Max,
    "min": sp.Min,
    "pi": sp.pi,
    "E": sp.E,
}


class SymbolicExecutionError(Exception):
    """Wraps errors raised while handling symbolic operations."""


def _build_local_dict(
    context: ExpressionContext,
    extra_allowed: Iterable[str] | None = None,
) -> Tuple[Dict[str, object], Dict[str, float]]:
    local_dict: Dict[str, object] = dict(_ALLOWED_FUNCTIONS)
    if extra_allowed:
        for name in extra_allowed:
            sym_attr = getattr(sp, name, None)
            if callable(sym_attr) or isinstance(sym_attr, sp.Basic):
                local_dict[name] = sym_attr

    substitutions: Dict[str, float] = {}
    for name, value in {**context.variables, **context.parameters}.items():
        symbol = sp.symbols(name)
        local_dict[name] = symbol
        if isinstance(value, (int, float)):
            substitutions[symbol] = float(value)
        elif isinstance(value, str):
            substitutions[symbol] = sp.sympify(value)
    return local_dict, substitutions


def _parse_expression(
    expression: str,
    context: ExpressionContext,
    extra_allowed: Iterable[str] | None,
) -> Tuple[sp.Expr, Dict[sp.Symbol, float]]:
    local_dict, substitutions = _build_local_dict(context, extra_allowed)
    try:
        parsed = parse_expr(expression, local_dict=local_dict, transformations=_TRANSFORMATIONS)
    except Exception as exc:  # sympy raises many specific subclasses
        raise SymbolicExecutionError(f"Failed to parse expression: {exc}") from exc
    return sp.sympify(parsed), substitutions


def _approximate(expr: sp.Expr, substitutions: Dict[sp.Symbol, float]) -> float | None:
    if not substitutions:
        return None
    try:
        numeric = expr.evalf(subs=substitutions)
        if numeric.is_real:
            return float(numeric)
    except Exception:
        return None
    return None


def _build_codegen(expr: sp.Expr, options: CodegenOptions) -> Dict[str, str]:
    targets = {target.lower() for target in options.targets}
    code: Dict[str, str] = {}
    for target in targets:
        if target == "python":
            code[target] = sp.pycode(expr)
        elif target in {"c", "cc"}:
            code[target] = sp.ccode(expr)
        elif target == "fortran":
            code[target] = sp.fcode(expr)
        else:
            raise SymbolicExecutionError(f"Unsupported codegen target: {target}")
    return code


def execute_symbolic_operation(
    operation: SymbolicOperation,
    expression: str,
    context: ExpressionContext,
    variable: str | None,
    order: int | None,
    codegen: CodegenOptions,
    extra_allowed_functions: Iterable[str] | None = None,
) -> SymbolicResult:
    expr, substitutions = _parse_expression(expression, context, extra_allowed_functions)
    symbol = sp.symbols(variable) if variable else None

    if operation == SymbolicOperation.SIMPLIFY:
        result_expr = sp.factor(sp.simplify(expr))
    elif operation == SymbolicOperation.DERIVATIVE:
        target = symbol or sp.Symbol("x")
        result_expr = sp.diff(expr, target)
    elif operation == SymbolicOperation.INTEGRAL:
        target = symbol or sp.Symbol("x")
        result_expr = sp.integrate(expr, target)
    elif operation == SymbolicOperation.SOLVE:
        target = symbol or sp.Symbol("x")
        solutions = sp.solve(sp.Eq(expr, 0), target, dict=True)
        list_repr = [sp.simplify(sol[target]) for sol in solutions if target in sol]
        result_expr = sp.FiniteSet(*list_repr) if list_repr else sp.EmptySet
    elif operation == SymbolicOperation.SERIES:
        target = symbol or sp.Symbol("x")
        series_order = order or 6
        series_expr = sp.series(expr, target, 0, series_order)
        result_expr = sp.expand(series_expr.removeO())
    elif operation == SymbolicOperation.CODEGEN:
        result_expr = sp.factor(sp.simplify(expr))
    else:
        raise SymbolicExecutionError(f"Unsupported operation: {operation}")

    series_terms: Iterable[str] | None = None
    if operation == SymbolicOperation.SERIES:
        series_terms = [str(term) for term in result_expr.as_ordered_terms()]

    code_map: Dict[str, str] = {}
    if operation in {SymbolicOperation.CODEGEN, SymbolicOperation.SIMPLIFY}:
        code_map = _build_codegen(result_expr, codegen)

    latex_repr = sp.latex(result_expr)
    approx = _approximate(result_expr, substitutions)

    return SymbolicResult(
        canonical=str(result_expr),
        latex=latex_repr,
        approx_value=approx,
        code=code_map,
        series_terms=list(series_terms) if series_terms else None,
    )
