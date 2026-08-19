import hmac
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class RemoteAuthTest(unittest.TestCase):
    def test_hmac_compare(self):
        token = "secret-token"
        good = "secret-token"
        bad = "wrong-token"
        self.assertTrue(hmac.compare_digest(good, token))
        self.assertFalse(hmac.compare_digest(bad, token))

    def test_missing_key_denies(self):
        from interfaces.remote import server
        os.environ.pop("MIKE_REMOTE_KEY", None)
        server._token = ""
        self.assertFalse(server._authorized("Bearer anything"))

    def test_correct_key_allows(self):
        from interfaces.remote import server
        server._token = "abc123"
        self.assertTrue(server._authorized("Bearer abc123"))
        self.assertFalse(server._authorized("Bearer nope"))

    def test_index_page_exists(self):
        from interfaces.remote import server
        self.assertIn("MIKE", server._INDEX_HTML)
        self.assertIn("SpeechRecognition", server._INDEX_HTML)
        self.assertIn("/api/chat", server._INDEX_HTML)

    def test_lan_ip_returns_string(self):
        from interfaces.remote.server import _lan_ip
        ip = _lan_ip()
        self.assertIsInstance(ip, str)
        self.assertIn(".", ip)


if __name__ == "__main__":
    unittest.main()