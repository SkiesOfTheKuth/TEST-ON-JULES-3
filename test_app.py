import unittest
import json
from app import app

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

if __name__ == '__main__':
    unittest.main()