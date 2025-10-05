"""Propagation helpers for the OpenTelemetry stub."""

from __future__ import annotations

from typing import Mapping, MutableMapping


def extract(headers: Mapping[str, str] | None = None):
    return headers or {}


def inject(carrier: MutableMapping[str, str], context=None) -> None:  # pragma: no cover - no-op
    return None
