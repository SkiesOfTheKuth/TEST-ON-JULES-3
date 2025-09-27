import unittest
import math
from logic import (
    add, subtract, multiply, divide, power, sqrt,
    sin, cos, tan, sind, cosd, tand,
    asin, acos, atan,
    log, log10, factorial,
    sinh, cosh, tanh,
    pi, e
)

class TestLogic(unittest.TestCase):

    def test_constants(self):
        """Test if the constants are defined correctly."""
        self.assertAlmostEqual(pi, math.pi)
        self.assertAlmostEqual(e, math.e)

    def test_add(self):
        """Test addition function."""
        self.assertEqual(add(1, 2), 3)
        self.assertEqual(add(-1, 1), 0)
        self.assertEqual(add(-1, -1), -2)

    def test_subtract(self):
        """Test subtraction function."""
        self.assertEqual(subtract(10, 5), 5)
        self.assertEqual(subtract(-1, 1), -2)

    def test_multiply(self):
        """Test multiplication function."""
        self.assertEqual(multiply(3, 7), 21)
        self.assertEqual(multiply(-1, 1), -1)

    def test_divide(self):
        """Test division function, including division by zero."""
        self.assertEqual(divide(10, 2), 5)
        self.assertEqual(divide(5, 2), 2.5)
        with self.assertRaisesRegex(ValueError, r"Division by zero is not allowed\."):
            divide(10, 0)

    def test_power(self):
        """Test power function."""
        self.assertEqual(power(2, 3), 8)
        self.assertEqual(power(4, 0.5), 2)

    def test_sqrt(self):
        """Test square root function, including negative input."""
        self.assertEqual(sqrt(16), 4)
        with self.assertRaisesRegex(ValueError, r"Square root of a negative number is not real\."):
            sqrt(-1)

    # --- Radian Trigonometric Tests ---
    def test_sin(self):
        """Test sine function with radians."""
        self.assertAlmostEqual(sin(0), 0)
        self.assertAlmostEqual(sin(math.pi / 2), 1)

    def test_cos(self):
        """Test cosine function with radians."""
        self.assertAlmostEqual(cos(0), 1)
        self.assertAlmostEqual(cos(math.pi), -1)

    def test_tan(self):
        """Test tangent function with radians."""
        self.assertAlmostEqual(tan(0), 0)
        self.assertAlmostEqual(tan(math.pi / 4), 1)

    # --- Degree Trigonometric Tests ---
    def test_sind(self):
        """Test sine function with degrees."""
        self.assertAlmostEqual(sind(0), 0)
        self.assertAlmostEqual(sind(90), 1)

    def test_cosd(self):
        """Test cosine function with degrees."""
        self.assertAlmostEqual(cosd(0), 1)
        self.assertAlmostEqual(cosd(180), -1)

    def test_tand(self):
        """Test tangent function with degrees."""
        self.assertAlmostEqual(tand(0), 0)
        self.assertAlmostEqual(tand(45), 1)
        with self.assertRaisesRegex(ValueError, r"Tangent is undefined for odd multiples of 90 degrees\."):
            tand(90)
        with self.assertRaisesRegex(ValueError, r"Tangent is undefined for odd multiples of 90 degrees\."):
            tand(270)
        with self.assertRaisesRegex(ValueError, r"Tangent is undefined for odd multiples of 90 degrees\."):
            tand(-90)

    # --- Inverse Trigonometric Tests ---
    def test_asin(self):
        """Test arc sine function."""
        self.assertAlmostEqual(asin(1), math.pi / 2)
        with self.assertRaisesRegex(ValueError, r"Arc sine domain is \[-1, 1]\."):
            asin(2)

    def test_acos(self):
        """Test arc cosine function."""
        self.assertAlmostEqual(acos(1), 0)
        with self.assertRaisesRegex(ValueError, r"Arc cosine domain is \[-1, 1]\."):
            acos(-2)

    def test_atan(self):
        """Test arc tangent function."""
        self.assertAlmostEqual(atan(1), math.pi / 4)

    # --- Logarithmic Tests ---
    def test_log(self):
        """Test natural logarithm function."""
        self.assertAlmostEqual(log(math.e), 1)
        with self.assertRaisesRegex(ValueError, r"Logarithm is undefined for non-positive numbers\."):
            log(0)

    def test_log10(self):
        """Test base-10 logarithm function."""
        self.assertAlmostEqual(log10(100), 2)
        with self.assertRaisesRegex(ValueError, r"Logarithm is undefined for non-positive numbers\."):
            log10(-10)

    # --- Factorial Test ---
    def test_factorial(self):
        """Test factorial function."""
        self.assertEqual(factorial(5), 120)
        with self.assertRaisesRegex(ValueError, r"Factorial is only defined for non-negative integers\."):
            factorial(-1)
        with self.assertRaisesRegex(ValueError, r"Factorial is only defined for non-negative integers\."):
            factorial(1.5)

    # --- Hyperbolic Tests ---
    def test_sinh(self):
        """Test hyperbolic sine function."""
        self.assertAlmostEqual(sinh(0), 0)
        self.assertAlmostEqual(sinh(1), math.sinh(1))

    def test_cosh(self):
        """Test hyperbolic cosine function."""
        self.assertAlmostEqual(cosh(0), 1)
        self.assertAlmostEqual(cosh(1), math.cosh(1))

    def test_tanh(self):
        """Test hyperbolic tangent function."""
        self.assertAlmostEqual(tanh(0), 0)
        self.assertAlmostEqual(tanh(1), math.tanh(1))

if __name__ == '__main__':
    unittest.main()