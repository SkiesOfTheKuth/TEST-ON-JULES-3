"""Compatibility helpers for Python version differences."""

from __future__ import annotations

from typing import Any


class _Missing:
    """Sentinel used to detect whether a default value was provided."""


_MISSING = _Missing()

try:
    from builtins import anext as _py_anext  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - best effort import for <3.10
    _py_anext = None  # type: ignore[assignment]


async def anext_async(aiter: Any, default: Any = _MISSING) -> Any:
    """Await the next item from an async iterator with optional default."""

    try:
        return await aiter.__anext__()  # type: ignore[attr-defined]
    except StopAsyncIteration:
        if default is _MISSING:
            raise
        return default


def anext_sync(iterator: Any, default: Any = _MISSING) -> Any:
    """Retrieve the next item from a sync iterator with optional default."""

    if _py_anext is not None:
        if default is _MISSING:
            return _py_anext(iterator)  # pragma: no cover - python >=3.10
        return _py_anext(iterator, default)

    try:
        return next(iterator)
    except StopIteration:
        if default is _MISSING:
            raise
        return default


__all__ = ["anext_async", "anext_sync"]
