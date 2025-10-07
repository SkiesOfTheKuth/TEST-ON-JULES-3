"""Entry point executed inside the sandbox subprocess."""
from __future__ import annotations

import json
import resource
import signal
import sys
import time
from dataclasses import asdict
from typing import Any, Dict

from . import operations
from .config import Settings


class SandboxFailure(Exception):
    """Internal sandbox exception."""


def _apply_resource_limits(settings: Settings) -> None:
    """Apply CPU and memory resource ceilings."""

    memory_bytes = settings.sandbox_memory_limit_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_CPU, (settings.sandbox_cpu_time_seconds, settings.sandbox_cpu_time_seconds))


def _install_signal_handlers(settings: Settings) -> None:
    """Install fail-fast signal handlers."""

    def _handler(signum: int, _: Any) -> None:
        raise SandboxFailure(f"Sandbox interrupted by signal {signum}.")

    signal.signal(signal.SIGXCPU, _handler)
    signal.signal(signal.SIGTERM, _handler)


def _guard_imports(settings: Settings) -> None:
    """Disallow importing unsafe modules within the sandbox."""

    blocked = set(settings.sandbox_blocked_modules)
    builtins_obj = __builtins__
    if isinstance(builtins_obj, dict):
        original_import = builtins_obj["__import__"]
    else:
        original_import = builtins_obj.__import__  # type: ignore[attr-defined]

    def _restricted_import(name: str, globals: Dict[str, Any] | None = None, locals: Dict[str, Any] | None = None, fromlist: Any = (), level: int = 0):  # noqa: D417, ANN001
        root = name.split(".", 1)[0]
        if root in blocked:
            msg = f"Module '{root}' is not permitted in the symbolic sandbox."
            raise ImportError(msg)
        return original_import(name, globals, locals, fromlist, level)

    if isinstance(builtins_obj, dict):
        builtins_obj["__import__"] = _restricted_import
    else:  # pragma: no cover - exercised at runtime only
        builtins_obj.__import__ = _restricted_import  # type: ignore[attr-defined]


def _success_payload(result: operations.OperationResult, diagnostics: Dict[str, Any]) -> Dict[str, Any]:
    payload = asdict(result)
    payload["diagnostics"] = diagnostics
    return payload


def _execute(operation: str, payload: Dict[str, Any], settings: Settings) -> Dict[str, Any]:
    """Dispatch the requested symbolic operation."""

    canonicalize = payload.get("canonicalize", True)
    if operation == "simplify":
        request = payload
        op_result = operations.simplify_expression(
            expression=request["expression"],
            variables=request.get("variables", []),
            method=request.get("method"),
            canonicalize=canonicalize,
        )
    elif operation == "derivative":
        request = payload
        op_result = operations.differentiate_expression(
            expression=request["expression"],
            variables=request.get("variables", []),
            variable=request["variable"],
            order=request.get("order", 1),
            canonicalize=canonicalize,
        )
    elif operation == "integral":
        request = payload
        op_result = operations.integrate_expression(
            expression=request["expression"],
            variables=request.get("variables", []),
            variable=request["variable"],
            lower_limit=request.get("lower_limit"),
            upper_limit=request.get("upper_limit"),
            canonicalize=canonicalize,
        )
    elif operation == "solve":
        request = payload
        op_result = operations.solve_equation(
            equation=request["equation"],
            variable=request["variable"],
            parameters=request.get("parameters", []),
            canonicalize=canonicalize,
        )
    elif operation == "series":
        request = payload
        op_result = operations.series_expansion(
            expression=request["expression"],
            variables=request.get("variables", []),
            variable=request["variable"],
            point=request.get("point", "0"),
            order=request.get("order", 6),
            canonicalize=canonicalize,
        )
    elif operation == "codegen":
        request = payload
        op_result = operations.generate_code(
            expression=request["expression"],
            variables=request.get("variables", []),
            target=request.get("target", settings.default_codegen_target),
            function_name=request.get("function_name", "symbolic_kernel"),
            emit_header=request.get("emit_header", False),
            canonicalize=canonicalize,
        )
    else:  # pragma: no cover - validated before invocation
        raise SandboxFailure(f"Unsupported operation '{operation}'.")

    return _success_payload(op_result, diagnostics={})


def main() -> None:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Operation argument required."}))
        sys.exit(1)

    operation = sys.argv[1]
    raw = sys.stdin.read() or "{}"

    try:
        parsed = json.loads(raw)
        payload = parsed.get("payload", {})
        settings = Settings(**parsed.get("config", {}))
    except Exception as exc:  # pragma: no cover - indicates upstream bug
        print(json.dumps({"error": f"Invalid sandbox payload: {exc}"}))
        sys.exit(1)

    diagnostics: Dict[str, Any] = {}
    try:
        _apply_resource_limits(settings)
        _install_signal_handlers(settings)
        _guard_imports(settings)
        start = time.monotonic()
        result = _execute(operation, payload, settings)
        diagnostics = result.get("diagnostics", {})
        diagnostics["runtime_ms"] = (time.monotonic() - start) * 1000
        result["diagnostics"] = diagnostics
    except SandboxFailure as exc:
        print(json.dumps({"error": str(exc), "diagnostics": diagnostics}))
        sys.exit(1)
    except Exception as exc:  # pragma: no cover - ensures crash safety
        print(json.dumps({"error": f"Unhandled sandbox error: {exc}", "diagnostics": diagnostics}))
        sys.exit(1)
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
