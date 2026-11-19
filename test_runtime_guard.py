import unittest

import runtime


class ApiKeyGuardTests(unittest.TestCase):
    def test_loopback_without_key_is_allowed(self):
        for host in ('127.0.0.1', 'localhost', '::1'):
            self.assertIsNone(runtime.api_key_error(host, ''))

    def test_exposed_host_without_key_is_rejected(self):
        for key in ('', '   '):
            self.assertIn('EKYC_API_KEY', runtime.api_key_error('0.0.0.0', key))

    def test_exposed_host_with_key_is_allowed(self):
        self.assertIsNone(runtime.api_key_error('0.0.0.0', 'secret'))


if __name__ == '__main__':
    unittest.main()
