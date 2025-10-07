"""Sandbox execution helpers for the symbolic engine."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict

from .config import Settings, get_settings


class SandboxExecutionError(RuntimeError):
    """Raised when the sandbox cannot produce a valid result."""

    def __init__(self, message: str, diagnostics: Dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or {}


_SUSPICIOUS_PATTERNS = (
    re.compile(r"__"),
    re.compile(r"\bimport\b", re.IGNORECASE),
    re.compile(r"\beval\b", re.IGNORECASE),
    re.compile(r"\bexec\b", re.IGNORECASE),
    re.compile(r"\bos\b", re.IGNORECASE),
    re.compile(r"\bsubprocess\b", re.IGNORECASE),
)


def _ensure_safe_payload(payload: Dict[str, Any]) -> None:
    """Validate that user supplied strings do not contain unsafe tokens."""

    for key, value in payload.items():
        if isinstance(value, str):
            for pattern in _SUSPICIOUS_PATTERNS:
                if pattern.search(value):
                    msg = f"Field '{key}' contains disallowed token for sandbox execution."
                    raise SandboxExecutionError(msg)
        elif isinstance(value, dict):
            _ensure_safe_payload(value)
        elif isinstance(value, (list, tuple)):
            for item in value:
                if isinstance(item, (str, dict, list, tuple)):
                    _ensure_safe_payload({"nested": item} if not isinstance(item, str) else {"nested": item})


def run_operation(operation: str, payload: Dict[str, Any], settings: Settings | None = None) -> Dict[str, Any]:
    """Execute an operation within the sandbox runner."""

    config = settings or get_settings()
    _ensure_safe_payload(payload)

    runner_module = "services.symbolic_engine.app.sandbox_runner"
    command = [sys.executable, "-m", runner_module, operation]

    cwd = Path(__file__).resolve().parents[2]
    start_time = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            input=json.dumps({"payload": payload, "config": config.dict()}),
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=config.sandbox_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - relies on system timing
        raise SandboxExecutionError("Sandbox execution timed out.") from exc

    runtime_ms = (time.monotonic() - start_time) * 1000

    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        raise SandboxExecutionError(
            "Sandbox process exited with failure.",
            diagnostics={
                "stderr": stderr,
                "runtime_ms": runtime_ms,
                "return_code": completed.returncode,
            },
        )

    try:
        data = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:  # pragma: no cover - indicates runner bug
        raise SandboxExecutionError("Failed to decode sandbox output.") from exc

    if "error" in data:
        raise SandboxExecutionError(
            data["error"],
            diagnostics={
                **{k: v for k, v in data.get("diagnostics", {}).items()},
                "runtime_ms": runtime_ms,
            },
        )

    data.setdefault("diagnostics", {})
    data["diagnostics"].update(
        {
            "runtime_ms": runtime_ms,
            "module_allowlist": list(config.sandbox_allowed_modules),
            "memory_limit_mb": config.sandbox_memory_limit_mb,
            "cpu_limit_seconds": config.sandbox_cpu_time_seconds,
        }
    )
    return data
