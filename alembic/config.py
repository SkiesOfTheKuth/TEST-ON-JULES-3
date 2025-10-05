"""Minimal Alembic config stub."""

from __future__ import annotations

from typing import Any, Dict


class Config:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.options: Dict[str, Any] = {}

    def set_main_option(self, key: str, value: str) -> None:
        self.options[key] = value


__all__ = ["Config"]
