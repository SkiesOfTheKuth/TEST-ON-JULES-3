"""Core arithmetic helpers used by the calculator stack."""

from __future__ import annotations

import math
from typing import SupportsFloat


Number = SupportsFloat


def add(x: Number, y: Number) -> float:
    """Add two numbers."""

    return float(x) + float(y)


def subtract(x: Number, y: Number) -> float:
    """Subtract ``y`` from ``x``."""

    return float(x) - float(y)


def multiply(x: Number, y: Number) -> float:
    """Multiply two numbers."""

    return float(x) * float(y)


def divide(x: Number, y: Number) -> float:
    """Divide ``x`` by ``y`` ensuring ``y`` is non-zero."""

    if float(y) == 0.0:
        raise ValueError("Cannot divide by zero")

    return float(x) / float(y)


def power(x: Number, y: Number) -> float:
    """Raise ``x`` to the power of ``y``."""

    return float(x) ** float(y)


def sqrt(x: Number) -> float:
    """Return the non-negative square root of ``x``."""

    value = float(x)
    if value < 0:
        raise ValueError("Cannot take the square root of a negative number")

    return math.sqrt(value)