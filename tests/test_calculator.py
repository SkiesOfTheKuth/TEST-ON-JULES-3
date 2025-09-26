import unittest
import sys
import os
import math

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.logic import (
    add, subtract, multiply, divide, power, sqrt, sin, cos, tan, log, log10, factorial,
    absolute, round_number
)

class TestCalculator(unittest.TestCase):

    def test_add(self):
        self.assertEqual(add(1, 2), 3)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(-1, -1), -2)
        self.assertEqual(add(0, 0), 0)
        self.assertEqual(add(1.5, 2.5), 4.0)

    def test_subtract(self):
        self.assertEqual(subtract(10, 5), 5)
        self.assertEqual(subtract(-1, 1), -2)
        self.assertEqual(subtract(-1, -1), 0)
        self.assertEqual(subtract(5, 10), -5)
        self.assertEqual(subtract(2.5, 1.5), 1.0)

    def test_multiply(self):
        self.assertEqual(multiply(3, 7), 21)
        self.assertEqual(multiply(-1, 1), -1)
        self.assertEqual(multiply(-1, -1), 1)
        self.assertEqual(multiply(0, 100), 0)
        self.assertEqual(multiply(1.5, 2), 3.0)

    def test_divide(self):
        self.assertEqual(divide(10, 2), 5)
        self.assertEqual(divide(-10, 2), -5)
        self.assertEqual(divide(-10, -2), 5)
        self.assertEqual(divide(5, 2), 2.5)
        self.assertEqual(divide(0, 1), 0)
        with self.assertRaises(ValueError):
            divide(10, 0)

    def test_power(self):
        self.assertEqual(power(2, 3), 8)
        self.assertEqual(power(5, 0), 1)
        self.assertEqual(power(-2, 3), -8)
        self.assertEqual(power(4, 0.5), 2)

    def test_sqrt(self):
        self.assertEqual(sqrt(16), 4)
        self.assertEqual(sqrt(0), 0)
        self.assertAlmostEqual(sqrt(2), 1.41421356, places=7)
        self.assertAlmostEqual(sqrt(0.1), math.sqrt(0.1))
        with self.assertRaises(ValueError):
            sqrt(-1)

    def test_sin(self):
        self.assertAlmostEqual(sin(0), 0)
        self.assertAlmostEqual(sin(90), 1)
        self.assertAlmostEqual(sin(180), 0)
        self.assertAlmostEqual(sin(270), -1)

    def test_cos(self):
        self.assertAlmostEqual(cos(0), 1)
        self.assertAlmostEqual(cos(90), 0)
        self.assertAlmostEqual(cos(180), -1)
        self.assertAlmostEqual(cos(270), 0)

    def test_tan(self):
        self.assertAlmostEqual(tan(0), 0)
        self.assertAlmostEqual(tan(45), 1)

    def test_log(self):
        self.assertAlmostEqual(log(1), 0)
        self.assertAlmostEqual(log(math.e), 1)
        with self.assertRaises(ValueError):
            log(0)
        with self.assertRaises(ValueError):
            log(-1)

    def test_log10(self):
        self.assertAlmostEqual(log10(1), 0)
        self.assertAlmostEqual(log10(10), 1)
        self.assertAlmostEqual(log10(100), 2)
        with self.assertRaises(ValueError):
            log10(0)
        with self.assertRaises(ValueError):
            log10(-1)

    def test_factorial(self):
        self.assertEqual(factorial(0), 1)
        self.assertEqual(factorial(1), 1)
        self.assertEqual(factorial(5), 120)
        with self.assertRaises(ValueError):
            factorial(-1)
        with self.assertRaises(ValueError):
            factorial(1.5)

    def test_absolute(self):
        self.assertEqual(absolute(10), 10)
        self.assertEqual(absolute(-10), 10)
        self.assertEqual(absolute(0), 0)
        self.assertAlmostEqual(absolute(-5.5), 5.5)

    def test_round_number(self):
        self.assertEqual(round_number(3.14159), 3)
        self.assertEqual(round_number(3.14159, 2), 3.14)
        self.assertEqual(round_number(3.5), 4)
        self.assertEqual(round_number(2.5), 2)
        self.assertEqual(round_number(-2.5), -2)
        self.assertEqual(round_number(-3.5), -4)

if __name__ == '__main__':
    unittest.main()