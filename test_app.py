import unittest
import json
from app import app

class TestApp(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_index(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Web Calculator', response.data)

    def test_calculate_valid_expression(self):
        payload = {'expression': '2 + 2'}
        response = self.app.post('/calculate', data=json.dumps(payload), content_type='application/json')
        data = json.loads(response.data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['result'], 4)

    def test_calculate_invalid_expression(self):
        payload = {'expression': '2 +'}
        response = self.app.post('/calculate', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_calculate_no_expression(self):
        payload = {}
        response = self.app.post('/calculate', data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        data = json.loads(response.data)
        self.assertIn('error', data)

    def test_calculate_with_logic_functions(self):
        test_cases = [
            ('sqrt(16)', 4),
            ('power(2, 3)', 8),
            ('sin(90)', 1.0),
            ('cos(0)', 1.0),
            ('tan(45)', 1.0),
            ('log(1)', 0),
            ('log10(100)', 2),
            ('factorial(5)', 120),
            ('percentage(10, 50)', 5)
        ]
        for expression, expected_result in test_cases:
            with self.subTest(expression=expression):
                payload = {'expression': expression}
                response = self.app.post('/calculate', data=json.dumps(payload), content_type='application/json')
                data = json.loads(response.data)
                self.assertEqual(response.status_code, 200)
                self.assertAlmostEqual(data['result'], expected_result, places=7)

if __name__ == '__main__':
    unittest.main()