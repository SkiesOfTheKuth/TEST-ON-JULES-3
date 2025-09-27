import unittest
import math
from logic import add, subtract, multiply, divide, power, sqrt, sin, cos, tan, log, log10, factorial, percentage

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
        with self.assertRaises(ValueError):
            sqrt(-1)

    def test_sin(self):
        self.assertAlmostEqual(sin(0), 0)
        self.assertAlmostEqual(sin(90), 1)
        self.assertAlmostEqual(sin(180), 0)
        self.assertAlmostEqual(sin(270), -1)
        self.assertAlmostEqual(sin(360), 0)

    def test_cos(self):
        self.assertAlmostEqual(cos(0), 1)
        self.assertAlmostEqual(cos(90), 0)
        self.assertAlmostEqual(cos(180), -1)
        self.assertAlmostEqual(cos(270), 0)
        self.assertAlmostEqual(cos(360), 1)

    def test_tan(self):
        self.assertAlmostEqual(tan(0), 0)
        self.assertAlmostEqual(tan(45), 1)
        self.assertAlmostEqual(tan(180), 0)
        with self.assertRaises(ValueError):
            tan(90)
        with self.assertRaises(ValueError):
            tan(270)

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

    def test_percentage(self):
        self.assertEqual(percentage(10, 100), 10)
        self.assertEqual(percentage(50, 200), 100)
        self.assertEqual(percentage(25, 80), 20)
        self.assertEqual(percentage(0, 100), 0)

if __name__ == '__main__':
    unittest.main()