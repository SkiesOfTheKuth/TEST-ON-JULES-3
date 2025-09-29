"""Unit tests for pure logic helpers."""

from __future__ import annotations

import math

import pytest

import logic


def test_add():
    assert logic.add(1, 2) == 3
    assert logic.add(-1, 1) == 0
    assert logic.add(-1, -1) == -2
    assert logic.add(0, 0) == 0
    assert logic.add(1.5, 2.5) == pytest.approx(4.0)


def test_subtract():
    assert logic.subtract(10, 5) == 5
    assert logic.subtract(-1, 1) == -2
    assert logic.subtract(-1, -1) == 0
    assert logic.subtract(5, 10) == -5
    assert logic.subtract(2.5, 1.5) == pytest.approx(1.0)


def test_multiply():
    assert logic.multiply(3, 7) == 21
    assert logic.multiply(-1, 1) == -1
    assert logic.multiply(-1, -1) == 1
    assert logic.multiply(0, 100) == 0
    assert logic.multiply(1.5, 2) == pytest.approx(3.0)


def test_divide():
    assert logic.divide(10, 2) == 5
    assert logic.divide(-10, 2) == -5
    assert logic.divide(-10, -2) == 5
    assert logic.divide(5, 2) == pytest.approx(2.5)
    assert logic.divide(0, 1) == 0

    with pytest.raises(ValueError):
        logic.divide(10, 0)


def test_power():
    assert logic.power(2, 3) == 8
    assert logic.power(5, 0) == 1
    assert logic.power(-2, 3) == -8
    assert logic.power(4, 0.5) == pytest.approx(2)


def test_sqrt():
    assert logic.sqrt(16) == 4
    assert logic.sqrt(0) == 0
    assert logic.sqrt(2) == pytest.approx(math.sqrt(2))

    with pytest.raises(ValueError):
        logic.sqrt(-1)

