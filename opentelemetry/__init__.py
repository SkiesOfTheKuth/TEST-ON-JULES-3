"""Minimal OpenTelemetry compatibility layer for offline tests."""

from __future__ import annotations

from . import context, propagate, trace

__all__ = ["trace", "context", "propagate"]
