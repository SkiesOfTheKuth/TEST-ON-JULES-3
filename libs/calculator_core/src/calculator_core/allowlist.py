"""Utilities for managing calculator sandbox allow lists."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping

from calculator_logic import (
    ABSOLUTE_FUNCTIONS,
    LOG_FUNCTIONS,
    TRIGONOMETRIC_FUNCTIONS,
    add,
    divide,
    factorial,
    multiply,
    power,
    round_number,
    sqrt,
    subtract,
)

DEFAULT_SYMBOLS: Dict[str, object] = {
    "add": add,
    "subtract": subtract,
    "multiply": multiply,
    "divide": divide,
    "power": power,
    "sqrt": sqrt,
    "factorial": factorial,
    "round": round_number,
    "round_number": round_number,
}
DEFAULT_SYMBOLS.update(TRIGONOMETRIC_FUNCTIONS)
DEFAULT_SYMBOLS.update(LOG_FUNCTIONS)
DEFAULT_SYMBOLS.update(ABSOLUTE_FUNCTIONS)


def default_allowlist() -> Dict[str, object]:
    """Return a copy of the default symbol allow list."""

    return dict(DEFAULT_SYMBOLS)


def filter_allowlist(symbols: Iterable[str]) -> Dict[str, object]:
    """Return a filtered allow list restricted to *symbols*."""

    filtered: Dict[str, object] = {}
    missing: list[str] = []
    for name in symbols:
        if name in DEFAULT_SYMBOLS:
            filtered[name] = DEFAULT_SYMBOLS[name]
        else:
            missing.append(name)
    if missing:
        available = ", ".join(sorted(DEFAULT_SYMBOLS))
        missing_str = ", ".join(sorted(missing))
        raise ValueError(
            f"Unknown allow list symbol(s): {missing_str}. Available symbols: {available}"
        )
    if not filtered:
        raise ValueError("Allow list must contain at least one permitted symbol")
    return filtered


def merge_allowlist(overrides: Mapping[str, object] | None = None) -> Dict[str, object]:
    """Return the default allow list merged with *overrides* if provided."""

    allowlist = default_allowlist()
    if overrides:
        for name, value in overrides.items():
            if name not in DEFAULT_SYMBOLS:
                raise ValueError(f"Override {name!r} is not a permitted calculator function")
            allowlist[name] = value
    return allowlist


__all__ = ["DEFAULT_SYMBOLS", "default_allowlist", "filter_allowlist", "merge_allowlist"]
