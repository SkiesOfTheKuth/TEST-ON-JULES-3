"""Deterministic math helpers that are safe to expose to the sandbox."""

from __future__ import annotations

import math
from typing import Dict

Number = float | int


def add(x: Number, y: Number) -> float:
    return float(x) + float(y)


def subtract(x: Number, y: Number) -> float:
    return float(x) - float(y)


def multiply(x: Number, y: Number) -> float:
    return float(x) * float(y)


def divide(x: Number, y: Number) -> float:
    if float(y) == 0.0:
        raise ValueError("Cannot divide by zero")
    return float(x) / float(y)


def power(x: Number, y: Number) -> float:
    return float(x) ** float(y)


def sqrt(x: Number) -> float:
    x_float = float(x)
    if x_float < 0.0:
        raise ValueError("Cannot take the square root of a negative number")
    return math.sqrt(x_float)


def sin(x: Number) -> float:
    return math.sin(math.radians(float(x)))


def cos(x: Number) -> float:
    return math.cos(math.radians(float(x)))


def tan(x: Number) -> float:
    return math.tan(math.radians(float(x)))


def log(x: Number) -> float:
    x_float = float(x)
    if x_float <= 0.0:
        raise ValueError("Cannot take the logarithm of a non-positive number")
    return math.log(x_float)


def log10(x: Number) -> float:
    x_float = float(x)
    if x_float <= 0.0:
        raise ValueError("Cannot take the logarithm of a non-positive number")
    return math.log10(x_float)


def factorial(x: Number) -> int:
    if not float(x).is_integer() or x < 0:
        raise ValueError("Factorial is only defined for non-negative integers")
    return math.factorial(int(x))


def absolute(x: Number) -> float:
    return abs(float(x))


def round_number(x: Number, ndigits: int = 0) -> float:
    return round(float(x), int(ndigits))


TRIGONOMETRIC_FUNCTIONS: Dict[str, object] = {
    "sin": sin,
    "cos": cos,
    "tan": tan,
}

LOG_FUNCTIONS: Dict[str, object] = {
    "log": log,
    "log10": log10,
}

ABSOLUTE_FUNCTIONS: Dict[str, object] = {
    "abs": absolute,
    "absolute": absolute,
}

__all__ = [
    "add",
    "subtract",
    "multiply",
    "divide",
    "power",
    "sqrt",
    "sin",
    "cos",
    "tan",
    "log",
    "log10",
    "factorial",
    "absolute",
    "round_number",
    "TRIGONOMETRIC_FUNCTIONS",
    "LOG_FUNCTIONS",
    "ABSOLUTE_FUNCTIONS",
]
