import unittest
import json
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.app import app

class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_calculate_endpoint(self):
        # Test a valid expression
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': '2 + 2'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['result'], 4)

        # Test a more complex expression
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': 'sqrt(16) + power(2, 3)'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['result'], 12)

    def test_invalid_expression(self):
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': '2 +* 2'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_no_expression(self):
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': ''}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_division_by_zero(self):
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': '10 / 0'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_advanced_functions(self):
        # Test abs()
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': 'abs(-15)'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['result'], 15)

        # Test round()
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': 'round(3.14159, 2)'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertEqual(data['result'], 3.14)

        # Test pi
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': 'pi'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertAlmostEqual(data['result'], 3.141592653589793)

        # Test e
        response = self.app.post('/calculate',
                                 data=json.dumps({'expression': 'e'}),
                                 content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertAlmostEqual(data['result'], 2.718281828459045)

if __name__ == '__main__':
    unittest.main()