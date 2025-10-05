"""Propagation helpers for the OpenTelemetry shim."""

from __future__ import annotations

from typing import Any, Dict


def inject(carrier: Dict[str, Any]) -> None:  # noqa: D401 - compatibility
    return None


def extract(carrier: Dict[str, Any]) -> Dict[str, Any]:  # noqa: D401 - compatibility
    return dict(carrier or {})


__all__ = ["inject", "extract"]
