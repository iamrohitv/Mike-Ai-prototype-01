import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.computer.contacts import resolve_detailed
from tools.computer.file_ops_tool import FileOpsTool
from tools.computer.whatsapp_tool import WhatsAppTool


class LocationFlowTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.tmp = tmp
        self.store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.tool = FileOpsTool(self.store, PolicyEngine())

    def tearDown(self):
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def test_create_without_location_asks(self):
        result = self.tool.run("create file mynotes.txt")
        self.assertIn("Where should I", result)
        self.assertIsNotNone(self.tool._pending_op)

    def test_location_answer_completes_pending(self):
        base = os.path.join(self.tmp.name, "desk")
        os.makedirs(base, exist_ok=True)
        self.tool.run("create file mynotes.txt")
        with mock.patch.object(self.tool, "_get_desktop_path",
                               return_value=base):
            result = self.tool.run("on desktop")
        self.assertIn("Created", result)
        self.assertTrue(os.path.isfile(os.path.join(base, "mynotes.txt")))
        self.assertIsNone(self.tool._pending_op)

    def test_full_path_still_direct(self):
        target = os.path.join(self.tmp.name, "direct.txt")
        result = self.tool.run(f"create file {target}")
        self.assertIn("Created", result)
        self.assertTrue(os.path.isfile(target))


class ContactFuzzyTest(unittest.TestCase):
    def test_typo_rhit_matches_rohit_as_fuzzy(self):
        book = {"rohit": "+919049923832"}
        num, key, fuzzy = resolve_detailed("rhit", book)
        self.assertEqual(num, "+919049923832")
        self.assertEqual(key, "rohit")
        self.assertTrue(fuzzy)  # close but not certain -> confirm first

    def test_exact_match_not_fuzzy(self):
        book = {"rohit": "+919049923832"}
        num, key, fuzzy = resolve_detailed("rohit", book)
        self.assertFalse(fuzzy)


class WhatsAppConfirmTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.tmp = tmp
        self.store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.tool = WhatsAppTool(self.store, PolicyEngine())
        self.tool.brain = None  # keep verbatim path deterministic

    def tearDown(self):
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    @mock.patch("tools.computer.whatsapp_tool.load_contacts",
                return_value={"rohit": "+919049923832"})
    def test_send_hi_to_rhit_asks_then_sends_on_yes(self, _book):
        self.tool._resolve_contact = lambda name: (
            "+919049923832" if name == "rohit" else None)

        with mock.patch(
            "tools.computer.whatsapp_tool.kit.sendwhatmsg_instantly"
        ) as send:
            first = self.tool.run("send hi to rhit")
        self.assertIn("rohit", first)
        self.assertIn("yes / no", first.lower())
        send.assert_not_called()

        with mock.patch(
            "tools.computer.whatsapp_tool.kit.sendwhatmsg_instantly"
        ) as send2:
            second = self.tool.run("ya ya you are right")
        send2.assert_called_once()
        self.assertIn('"hi"', second)

    @mock.patch("tools.computer.whatsapp_tool.load_contacts",
                return_value={"rohit": "+919049923832"})
    def test_no_cancels_pending(self, _book):
        self.tool.run("send hi to rhit")
        result = self.tool.run("no")
        self.assertIn("Cancelled", result)
        self.assertIsNone(self.tool._pending_send)

    def test_generic_send_shape_matches(self):
        self.assertTrue(self.tool.matches("send hi to rhit"))


class FileTypeExtractionTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.tmp = tmp
        self.store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.tool = FileOpsTool(self.store, PolicyEngine())
        self.base = os.path.join(tmp.name, "desk")
        os.makedirs(self.base, exist_ok=True)

    def tearDown(self):
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def _two_turn_create(self, request):
        first = self.tool.run(request)
        with mock.patch.object(self.tool, "_get_desktop_path",
                               return_value=self.base):
            second = self.tool.run("desktop")
        return first, second

    def test_python_type_word_becomes_extension(self):
        _f, second = self._two_turn_create(
            "create a python file of calculator app")
        self.assertIn("calculator app.py", second)
        self.assertTrue(os.path.isfile(
            os.path.join(self.base, "calculator app.py")))

    def test_markdown_type_word_becomes_extension(self):
        _f, second = self._two_turn_create(
            "create a markdown file on yourself")
        self.assertIn("yourself.md", second)
        self.assertTrue(os.path.isfile(
            os.path.join(self.base, "yourself.md")))


class LanguageMirrorTest(unittest.TestCase):
    def test_system_prompt_has_language_rule(self):
        from core.identity.identity import DEFAULT_SYSTEM_PROMPT
        self.assertIn("Hinglish", DEFAULT_SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()