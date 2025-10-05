"""Type helpers for the SQLAlchemy compatibility shim."""

from __future__ import annotations

from typing import Any


class TypeDecorator:
    impl: Any = None
    cache_ok = False

    def load_dialect_impl(self, dialect):  # noqa: D401, ARG002 - compatibility
        return self.impl


class JSON:
    pass


__all__ = ["TypeDecorator", "JSON"]
