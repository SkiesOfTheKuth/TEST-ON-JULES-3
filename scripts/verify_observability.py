#!/usr/bin/env python3
"""Lightweight offline checks for the observability baseline."""
from __future__ import annotations

import asyncio
import inspect
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # pragma: no cover - import guard for thin environments
    from fastapi import FastAPI
except Exception as exc:  # pragma: no cover - surfaced in script output
    FastAPI = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

PROM_CONTENT_TYPE = "text/plain; version=0.0.4"


def _prepare_import_path() -> None:
    """Ensure the repository's ``src`` layout is importable."""
    src_path = ROOT / "src"
    if src_path.exists() and str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))


def _invoke_metrics(app: FastAPI, path: str) -> Tuple[int, str]:
    """Call the metrics endpoint directly to obtain status and content type."""
    routes = list(getattr(app, "routes", []) or [])
    router = getattr(app, "router", None)
    if router is not None:
        routes.extend(getattr(router, "routes", []) or [])

    for route in routes:
        route_path = getattr(route, "path", getattr(route, "path_format", None))
        if route_path != path:
            if isinstance(route, tuple) and route[0] == path:
                handler = route[1]
            else:
                continue
        else:
            handler = getattr(route, "endpoint", getattr(route, "app", None))
        if handler is None:
            continue
        result = handler()
        if inspect.isawaitable(result):
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:  # pragma: no cover - fallback for sync contexts
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(result)  # pragma: no cover
        status = getattr(result, "status_code", 200)
        media_type = getattr(result, "media_type", "") or getattr(result, "headers", {}).get(
            "content-type", ""
        )
        if media_type:
            return status, media_type
        headers = getattr(result, "headers", {})
        return status, headers.get("content-type", "")
    raise RuntimeError(f"metrics endpoint {path} not found")


def check_gateway_installer() -> Tuple[str, bool, str]:
    if FastAPI is None:
        return ("gateway_metrics", False, f"dependencies unavailable: {_IMPORT_ERROR!r}")

    _prepare_import_path()
    try:
        from src.observability.prom_installer import install_prometheus_endpoint
    except Exception as exc:  # pragma: no cover - surfaced via script output
        return ("gateway_installer_import", False, repr(exc))

    app = FastAPI()
    install_prometheus_endpoint(app)
    install_prometheus_endpoint(app)

    status, media_type = _invoke_metrics(app, "/metrics")
    ok = status == 200 and PROM_CONTENT_TYPE in media_type
    return ("gateway_metrics", ok, media_type)


def check_worker_metrics_app() -> Tuple[str, bool, str]:
    if FastAPI is None:
        return ("worker_metrics", False, f"dependencies unavailable: {_IMPORT_ERROR!r}")

    _prepare_import_path()
    try:
        from worker.metrics_app import app
    except Exception as exc:  # pragma: no cover - surfaced via script output
        return ("worker_metrics_import", False, repr(exc))

    status, media_type = _invoke_metrics(app, "/metrics")
    ok = status == 200 and PROM_CONTENT_TYPE in media_type
    return ("worker_metrics", ok, media_type)


def run_worker_signals_pytest() -> Tuple[str, bool, str]:
    try:
        import pytest
    except Exception as exc:  # pragma: no cover - surfaced via script output
        return ("worker_signals_pytest", False, f"pytest unavailable: {exc!r}")

    result = pytest.main(["-q", "tests/metrics/test_worker_signals.py"])
    return ("worker_signals_pytest", result == 0, f"exit_code={result}")


def main(argv: List[str] | None = None) -> int:
    _ = argv  # unused but keeps signature flexible
    checks = [
        check_gateway_installer(),
        check_worker_metrics_app(),
        run_worker_signals_pytest(),
    ]

    failed = False
    for name, ok, info in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{name}: {status} — {info}")
        failed |= not ok

    return 1 if failed else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
