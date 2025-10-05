"""Context helpers for OpenTelemetry stubs."""

from __future__ import annotations


def attach(context):
    return context


def detach(token) -> None:  # pragma: no cover - no-op
    return None
