import unittest
import math
from logic import Calculator

class TestCalculator(unittest.TestCase):

    def setUp(self):
        self.calc = Calculator()

    def test_power(self):
        self.assertEqual(self.calc.power(2, 3), 8)
        self.assertEqual(self.calc.power(5, 0), 1)
        self.assertEqual(self.calc.power(-2, 3), -8)
        self.assertEqual(self.calc.power(4, 0.5), 2)

    def test_sqrt(self):
        self.assertEqual(self.calc.sqrt(16), 4)
        self.assertEqual(self.calc.sqrt(0), 0)
        self.assertAlmostEqual(self.calc.sqrt(2), 1.41421356, places=7)
        with self.assertRaises(ValueError):
            self.calc.sqrt(-1)

    def test_sin(self):
        self.assertAlmostEqual(self.calc.sin(0), 0)
        self.assertAlmostEqual(self.calc.sin(90), 1)
        self.assertAlmostEqual(self.calc.sin(180), 0)
        self.assertAlmostEqual(self.calc.sin(270), -1)
        self.assertAlmostEqual(self.calc.sin(360), 0)

    def test_cos(self):
        self.assertAlmostEqual(self.calc.cos(0), 1)
        self.assertAlmostEqual(self.calc.cos(90), 0)
        self.assertAlmostEqual(self.calc.cos(180), -1)
        self.assertAlmostEqual(self.calc.cos(270), 0)
        self.assertAlmostEqual(self.calc.cos(360), 1)

    def test_tan(self):
        self.assertAlmostEqual(self.calc.tan(0), 0)
        self.assertAlmostEqual(self.calc.tan(45), 1)
        self.assertAlmostEqual(self.calc.tan(180), 0)

    def test_asin(self):
        self.assertAlmostEqual(self.calc.asin(0), 0)
        self.assertAlmostEqual(self.calc.asin(1), 90)
        self.assertAlmostEqual(self.calc.asin(-1), -90)
        with self.assertRaises(ValueError):
            self.calc.asin(2)

    def test_acos(self):
        self.assertAlmostEqual(self.calc.acos(1), 0)
        self.assertAlmostEqual(self.calc.acos(0), 90)
        self.assertAlmostEqual(self.calc.acos(-1), 180)
        with self.assertRaises(ValueError):
            self.calc.acos(2)

    def test_atan(self):
        self.assertAlmostEqual(self.calc.atan(0), 0)
        self.assertAlmostEqual(self.calc.atan(1), 45)

    def test_log(self):
        self.assertAlmostEqual(self.calc.log(1), 0)
        self.assertAlmostEqual(self.calc.log(math.e), 1)
        with self.assertRaises(ValueError):
            self.calc.log(0)
        with self.assertRaises(ValueError):
            self.calc.log(-1)

    def test_log10(self):
        self.assertAlmostEqual(self.calc.log10(1), 0)
        self.assertAlmostEqual(self.calc.log10(10), 1)
        self.assertAlmostEqual(self.calc.log10(100), 2)
        with self.assertRaises(ValueError):
            self.calc.log10(0)
        with self.assertRaises(ValueError):
            self.calc.log10(-1)

    def test_factorial(self):
        self.assertEqual(self.calc.factorial(0), 1)
        self.assertEqual(self.calc.factorial(1), 1)
        self.assertEqual(self.calc.factorial(5), 120)
        with self.assertRaises(ValueError):
            self.calc.factorial(-1)
        with self.assertRaises(ValueError):
            self.calc.factorial(1.5)

    def test_percentage(self):
        self.assertEqual(self.calc.percentage(10, 100), 10)
        self.assertEqual(self.calc.percentage(50, 200), 100)
        self.assertEqual(self.calc.percentage(25, 80), 20)
        self.assertEqual(self.calc.percentage(0, 100), 0)

    def test_mod(self):
        self.assertEqual(self.calc.mod(10, 3), 1)
        self.assertEqual(self.calc.mod(10, 2), 0)
        self.assertEqual(self.calc.mod(5, 5), 0)

    def test_pi(self):
        self.assertEqual(self.calc.pi, math.pi)

    def test_e(self):
        self.assertEqual(self.calc.e, math.e)

if __name__ == '__main__':
    unittest.main()