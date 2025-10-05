"""Context helpers for the OpenTelemetry shim."""

from __future__ import annotations

from typing import Any


def attach(context: Any) -> Any:  # noqa: D401 - compatibility
    return context


def detach(token: Any) -> None:  # noqa: D401, ARG001 - compatibility
    return None


__all__ = ["attach", "detach"]
