import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.computer.messages_tool import MessagesTool
from tools.computer.message_providers import parse_chat_rows


class FakeRow:
    """Mimics a selenium web element just enough for parse_chat_rows."""

    def __init__(self, badges=None, titles=(), previews=()):
        self._badges = badges or []
        self._titles = list(titles)
        self._previews = list(previews)

    class _El:
        def __init__(self, text="", title=None):
            self._text = text
            self._title = title

        def get_attribute(self, name):
            if name == "aria-label":
                return self._text
            if name == "title":
                return self._title
            return None

        @property
        def text(self):
            return self._text

    def find_elements(self, by, selector):
        if "aria-label" in selector or "unread-count" in selector:
            return [self._El(t) for t in self._badges]
        if "title" in selector or "strong" in selector:
            return [self._El(t, t) for t in self._titles]
        if "dir=" in selector or "dir='" in selector:
            return [self._El(p) for p in self._previews]
        return []


class ParserTest(unittest.TestCase):
    def test_unread_row_parsed(self):
        rows = [FakeRow(badges=["3"], titles=["Mom"],
                        previews=["chat", "call me back"]),
                FakeRow()]  # no badge -> skipped
        chats = parse_chat_rows(rows)
        self.assertEqual(len(chats), 1)
        name, count, preview = chats[0]
        self.assertEqual(name, "Mom")
        self.assertEqual(count, 3)
        self.assertIn("call me back", preview)

    def test_non_digit_badge_ignored(self):
        rows = [FakeRow(badges=["typing…"], titles=["X"])]
        self.assertEqual(parse_chat_rows(rows), [])


class MessagesToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.tmp = tmp
        self.store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.tool = MessagesTool(self.store, PolicyEngine())

    def tearDown(self):
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def test_matches_variants(self):
        for text in ("read my new messages", "any new mails",
                     "check my whatsapp messages", "unread messages",
                     "check whatsapp"):
            self.assertTrue(self.tool.matches(text), text)

    def test_both_providers_reported(self):
        with mock.patch(
            "tools.computer.message_providers.fetch_unread_emails",
            return_value={"ok": True, "items": [("Rahul", "hi")],
                          "note": "1 unread mail(s)"},
        ), mock.patch(
            "tools.computer.message_providers.fetch_whatsapp_unreads",
            return_value={"ok": False, "items": [],
                          "note": "whatsapp: scan QR first"},
        ):
            result = self.tool.run("read my new messages")
        self.assertIn("[GMAIL]", result)
        self.assertIn("Rahul", result)
        self.assertIn("[WHATSAPP]", result)
        self.assertIn("scan QR", result)

    def test_empty_inboxes(self):
        with mock.patch(
            "tools.computer.message_providers.fetch_unread_emails",
            return_value={"ok": True, "items": [], "note": "0 unread"},
        ), mock.patch(
            "tools.computer.message_providers.fetch_whatsapp_unreads",
            return_value={"ok": True, "items": [], "note": "0 chat(s)"},
        ):
            result = self.tool.run("check messages")
        self.assertIn("nothing unread", result)


if __name__ == "__main__":
    unittest.main()