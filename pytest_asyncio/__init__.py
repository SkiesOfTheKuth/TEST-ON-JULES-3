"""Compatibility shim exposing a bundled pytest-asyncio plugin."""

from __future__ import annotations

from .plugin import fixture

pytest_plugins = ["pytest_asyncio.plugin"]

__all__ = ["fixture"]
