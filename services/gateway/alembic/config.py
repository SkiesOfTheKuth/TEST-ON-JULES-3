"""Stub of Alembic's configuration object."""

from __future__ import annotations

from typing import Any, Dict


class Config:
    def __init__(self, ini_path: str) -> None:
        self.ini_path = ini_path
        self._options: Dict[str, Any] = {}

    def set_main_option(self, key: str, value: str) -> None:
        self._options[key] = value
