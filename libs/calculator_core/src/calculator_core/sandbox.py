"""Subprocess-backed sandbox for running calculator expressions."""

from __future__ import annotations

import math
import multiprocessing as mp
import resource
import time
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any, Dict, Mapping, Optional

from asteval import Interpreter

from calculator_logic import (
    ABSOLUTE_FUNCTIONS,
    LOG_FUNCTIONS,
    TRIGONOMETRIC_FUNCTIONS,
    add,
    divide,
    factorial,
    multiply,
    power,
    round_number,
    sqrt,
    subtract,
)


@dataclass(slots=True)
class SandboxConfig:
    max_runtime_seconds: float = 0.25
    max_result_magnitude: float = 1e12
    max_memory_bytes: int = 64 * 1024 * 1024


@dataclass(slots=True)
class SandboxResult:
    ok: bool
    value: Optional[float]
    error: Optional[str]
    duration_ms: float


class SandboxRunner:
    """Execute expressions in a subprocess with strict limits."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()

    def run(self, expression: str, context: Mapping[str, Any] | None = None) -> SandboxResult:
        parent_conn, child_conn = mp.Pipe()
        process = mp.Process(
            target=_worker,
            args=(child_conn, expression, dict(context or {}), self._config),
            daemon=True,
        )
        start = time.perf_counter()
        process.start()
        process.join(self._config.max_runtime_seconds)
        duration_ms = (time.perf_counter() - start) * 1000.0

        if process.is_alive():
            process.kill()
            return SandboxResult(False, None, "Execution exceeded time limit", duration_ms)

        if not parent_conn.poll():
            return SandboxResult(False, None, "Sandbox produced no result", duration_ms)

        payload = parent_conn.recv()
        ok = payload.get("ok", False)
        if not ok:
            return SandboxResult(False, None, payload.get("error", "Unknown error"), duration_ms)

        value = payload.get("value")
        if value is None or not math.isfinite(value):
            return SandboxResult(False, None, "Non-finite result", duration_ms)
        if abs(value) > self._config.max_result_magnitude:
            return SandboxResult(False, None, "Result magnitude exceeded", duration_ms)
        return SandboxResult(True, float(value), None, duration_ms)


def _worker(conn: Connection, expression: str, context: Dict[str, Any], config: SandboxConfig) -> None:
    try:
        resource.setrlimit(resource.RLIMIT_AS, (config.max_memory_bytes, config.max_memory_bytes))
    except (ValueError, OSError):
        # Ignore platforms that do not support RLIMIT_AS.
        pass

    try:
        result = _evaluate(expression, context)
    except Exception as exc:  # noqa: BLE001
        conn.send({"ok": False, "error": str(exc)})
    else:
        conn.send({"ok": True, "value": result})
    finally:
        conn.close()


def _evaluate(expression: str, context: Mapping[str, Any]) -> float:
    interpreter = Interpreter(use_numpy=False)
    interpreter.symtable.clear()

    interpreter.symtable.update(
        {
            "add": add,
            "subtract": subtract,
            "multiply": multiply,
            "divide": divide,
            "power": power,
            "sqrt": sqrt,
            "factorial": factorial,
            "round": round_number,
        }
    )
    interpreter.symtable.update(TRIGONOMETRIC_FUNCTIONS)
    interpreter.symtable.update(LOG_FUNCTIONS)
    interpreter.symtable.update(ABSOLUTE_FUNCTIONS)

    sanitized_context: Dict[str, float] = {}
    for key, value in context.items():
        if not key.isidentifier():
            raise ValueError(f"Context key {key!r} is not a valid identifier")
        sanitized_context[key] = float(value)
    interpreter.symtable.update(sanitized_context)

    value = interpreter(expression)
    if interpreter.error:
        message = ", ".join(err.get_error() for err in interpreter.error)
        raise ValueError(message)
    return float(value)
