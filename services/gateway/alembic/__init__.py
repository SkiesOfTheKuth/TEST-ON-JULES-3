"""Minimal Alembic compatibility layer for unit tests."""

from __future__ import annotations

from .config import Config

__all__ = ["command", "Config"]


class _CommandModule:
    def upgrade(self, config: Config, revision: str) -> None:  # pragma: no cover - no-op
        return None


command = _CommandModule()
