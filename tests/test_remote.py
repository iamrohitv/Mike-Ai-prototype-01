import hmac
import os
import sys
import unittest
from unittest import mock

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


class LockoutTest(unittest.TestCase):
    def setUp(self):
        from interfaces.remote import server
        self.server = server
        server._token = "abc123"
        server._failed_attempts.clear()

    def test_five_failures_lockout(self):
        from interfaces.remote.server import _lockout_state, _record_failed
        for _ in range(5):
            _record_failed("1.2.3.4")
        self.assertGreater(_lockout_state("1.2.3.4"), 0)

    def test_other_ip_not_locked(self):
        from interfaces.remote.server import _lockout_state, _record_failed
        for _ in range(5):
            _record_failed("1.2.3.4")
        self.assertEqual(_lockout_state("9.9.9.9"), 0)


class TailnetTest(unittest.TestCase):
    @mock.patch("interfaces.remote.tailnet._find_bin", return_value="tailscale")
    @mock.patch("interfaces.remote.tailnet._run")
    def test_url_uses_magic_dns(self, mock_run, _mock_bin):
        from interfaces.remote.tailnet import tailnet_url
        mock_run.return_value = (
            '{"BackendState":"Running",'
            '"CurrentTailnet":{"MagicDNSEnabled":true},'
            '"Self":{"DNSName":"desktop-x.tail33fee4.ts.net.","Online":true,'
            '"TailscaleIPs":["100.71.122.55"]}}'
        )
        self.assertEqual(
            tailnet_url(port=8877),
            "http://desktop-x.tail33fee4.ts.net:8877",
        )

    @mock.patch("interfaces.remote.tailnet._find_bin", return_value="tailscale")
    @mock.patch("interfaces.remote.tailnet._run")
    def test_url_falls_back_to_ip(self, mock_run, _mock_bin):
        from interfaces.remote.tailnet import tailnet_url
        mock_run.return_value = (
            '{"BackendState":"Running",'
            '"CurrentTailnet":{"MagicDNSEnabled":false},'
            '"Self":{"DNSName":"desktop-x.tail33fee4.ts.net.","Online":true,'
            '"TailscaleIPs":["100.71.122.55"]}}'
        )
        self.assertEqual(tailnet_url(port=8877), "http://100.71.122.55:8877")

    @mock.patch("interfaces.remote.tailnet._find_bin", return_value="tailscale")
    @mock.patch("interfaces.remote.tailnet._run", return_value=None)
    def test_offline_returns_none(self, _mock_run, _mock_bin):
        from interfaces.remote.tailnet import tailnet_url
        self.assertIsNone(tailnet_url())


if __name__ == "__main__":
    unittest.main()