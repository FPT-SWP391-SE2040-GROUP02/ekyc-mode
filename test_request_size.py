import unittest

from fastapi.testclient import TestClient

from engine import MAX_BYTES
from server import MAX_REQUEST_BYTES, app


class RequestSizeLimitTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, base_url='http://127.0.0.1:8878')

    def test_limit_leaves_room_for_base64_of_a_max_image(self):
        self.assertGreater(MAX_REQUEST_BYTES, MAX_BYTES * 4 // 3)

    def test_declared_body_over_limit_is_rejected_before_reading(self):
        response = self.client.post(
            '/api/health', content=b'x', headers={'content-length': str(MAX_REQUEST_BYTES + 1)})
        self.assertEqual(response.status_code, 413)

    def test_body_within_limit_is_not_rejected_for_size(self):
        response = self.client.post('/api/health', content=b'x')
        self.assertNotEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
