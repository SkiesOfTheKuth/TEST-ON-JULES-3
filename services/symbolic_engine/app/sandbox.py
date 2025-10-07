"""SymPy sandbox runner executed inside a subprocess."""

from __future__ import annotations

import multiprocessing as mp
from typing import Dict, Optional

import sympy as sp

_ALLOWED_NAMES = {
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "log": sp.log,
    "ln": sp.log,
    "exp": sp.exp,
    "sqrt": sp.sqrt,
    "Abs": sp.Abs,
    "E": sp.E,
    "pi": sp.pi,
    "Symbol": sp.Symbol,
    "symbols": sp.symbols,
    "Integer": sp.Integer,
    "Rational": sp.Rational,
}


class SandboxError(RuntimeError):
    """Raised when the sandbox fails to evaluate an expression."""


class SandboxTimeoutError(SandboxError):
    """Raised when the sandbox process exceeds the allotted time."""


def _serialize_value(value: sp.Expr) -> Dict[str, object]:
    simplified = sp.simplify(value)
    payload: Dict[str, object] = {
        "simplified": str(simplified),
        "latex": sp.latex(simplified),
    }
    if simplified.free_symbols:
        payload["evaluated"] = str(simplified)
    else:
        try:
            numeric = sp.N(simplified)
            payload["evaluated"] = float(numeric)
        except (TypeError, ValueError):
            payload["evaluated"] = str(simplified)
    return payload


def _worker(expr: str, subs: Optional[Dict[str, float]], output: mp.Queue) -> None:
    sandbox_globals = {"__builtins__": {}}
    sandbox_locals = dict(_ALLOWED_NAMES)
    try:
        parsed = sp.sympify(expr, locals=sandbox_locals, globals=sandbox_globals, evaluate=True)
        simplified = sp.simplify(parsed)
        if subs:
            substitutions = {sp.Symbol(name): value for name, value in subs.items()}
            evaluated = simplified.subs(substitutions)
        else:
            evaluated = simplified
        payload = _serialize_value(evaluated)
        payload.setdefault("simplified", str(simplified))
        output.put(("ok", payload))
    except Exception as exc:  # noqa: BLE001
        output.put(("error", str(exc)))


def run_sandbox(expr: str, subs: Optional[Dict[str, float]] = None, timeout_s: float = 1.5) -> Dict[str, object]:
    """Execute a symbolic expression within a restricted subprocess."""

    result_queue: mp.Queue = mp.Queue(maxsize=1)
    process = mp.Process(target=_worker, args=(expr, subs, result_queue))
    process.start()
    process.join(timeout_s)
    try:
        if process.is_alive():
            process.terminate()
            process.join()
            raise SandboxTimeoutError(f"Timed out after {timeout_s:.2f}s")
        if result_queue.empty():
            raise SandboxError("No result returned from sandbox")
        status, payload = result_queue.get_nowait()
        if status == "ok":
            return payload
        raise SandboxError(str(payload))
    finally:
        result_queue.close()
        process.close()
