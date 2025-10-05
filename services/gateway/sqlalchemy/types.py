"""Minimal SQLAlchemy types used in the gateway tests."""

from __future__ import annotations


class TypeDecorator:
    cache_ok = True

    def __init__(self, *args, **kwargs) -> None:
        pass

    def load_dialect_impl(self, dialect):  # pragma: no cover - compatibility hook
        return self


class JSON:
    pass
