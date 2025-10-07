"""Lightweight Alembic script helpers for test environments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def from_config(config: Any) -> "ScriptDirectory":  # pragma: no cover - simple shim
    return ScriptDirectory(config)


@dataclass
class ScriptDirectory:
    """Minimal stand-in for Alembic's ScriptDirectory."""

    config: Any

    @classmethod
    def from_config(cls, config: Any) -> "ScriptDirectory":
        return cls(config)

    def get_current_head(self) -> str:
        return "head"


__all__ = ["ScriptDirectory", "from_config"]
