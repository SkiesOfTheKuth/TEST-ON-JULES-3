"""No-op Alembic command stubs."""

from __future__ import annotations

from typing import Any


def upgrade(config: Any, revision: str) -> None:  # noqa: D401, ARG002 - compatibility
    return None


__all__ = ["upgrade"]
