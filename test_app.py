import unittest
import json
import math
from app import app

class TestApp(unittest.TestCase):

    def setUp(self):
        """Set up the test client."""
        self.app = app.test_client()
        self.app.testing = True

    def _post_calculate(self, expression: str):
        """Helper function to send a POST request to the /calculate endpoint."""
        return self.app.post(
            '/calculate',
            data=json.dumps({'expression': expression}),
            content_type='application/json'
        )

    def test_valid_expressions(self):
        """Test a wide range of valid mathematical expressions."""
        test_cases = {
            '2 + 2': 4,
            'sqrt(16) + power(2, 3)': 12.0,
            'pi': math.pi,
            'e': math.e,
            'sind(90)': 1.0,
            'cosd(180)': -1.0,
            'tand(45)': 1.0,
            'log(e)': 1.0,
            'log10(100)': 2.0,
            'factorial(5)': 120,
            '2 * (3 + 4)': 14,
            'sinh(0)': 0,
            'cosh(0)': 1,
            'tanh(0)': 0,
            'asin(1)': math.pi / 2,
        }

        for expr, expected in test_cases.items():
            with self.subTest(expression=expr):
                response = self._post_calculate(expr)
                self.assertEqual(response.status_code, 200)
                data = json.loads(response.data)
                self.assertIn('result', data)
                self.assertAlmostEqual(data['result'], expected)

    def test_syntax_errors(self):
        """Test expressions with syntax errors."""
        response = self._post_calculate('2 +* 2')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertIn('SyntaxError', data['error'])

    def test_logic_errors(self):
        """Test expressions that should raise specific ValueErrors from the logic module."""
        test_cases = {
            '10 / 0': "division by zero",
            'sqrt(-4)': "Square root of a negative number is not real.",
            'log(0)': "Logarithm is undefined for non-positive numbers.",
            'log10(-1)': "Logarithm is undefined for non-positive numbers.",
            'asin(2)': "Arc sine domain is [-1, 1].",
            'acos(-2)': "Arc cosine domain is [-1, 1].",
            'factorial(-1)': "Factorial is only defined for non-negative integers."
        }

        for expr, error_msg in test_cases.items():
            with self.subTest(expression=expr):
                response = self._post_calculate(expr)
                self.assertEqual(response.status_code, 400)
                data = json.loads(response.data)
                self.assertIn('error', data)
                self.assertIn(error_msg, data['error'])

    def test_empty_or_missing_expression(self):
        """Test requests with empty or missing expression fields."""
        # Test empty expression string
        response = self._post_calculate('')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Expression cannot be empty.')

        # Test request with missing 'expression' key
        response = self.app.post('/calculate',
                                 data=json.dumps({'wrong_key': '2+2'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid request format.')

    def test_invalid_request_body(self):
        """Test a request with a malformed or non-JSON body."""
        response = self.app.post('/calculate',
                                 data="this is not json",
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertEqual(data['error'], 'Invalid request format.')

if __name__ == '__main__':
    unittest.main()