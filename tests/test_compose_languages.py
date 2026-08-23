import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.computer.compose_lang import extract_language, language_directive
from tools.computer.whatsapp_tool import WhatsAppTool


class ComposeLangTest(unittest.TestCase):
    def test_extract_explicit(self):
        self.assertEqual(extract_language("wish him in hinglish"), "hinglish")
        self.assertEqual(extract_language("IN Hindi"), "hindi")
        self.assertIsNone(extract_language("wish him happy birthday"))

    def test_directive_default_is_english(self):
        d = language_directive(None)
        self.assertIn("English", d)

    def test_directive_override(self):
        self.assertIn("HINGLISH", language_directive("hinglish"))


class WhatsAppLangFlowTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.tmp = tmp
        self.store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.tool = WhatsAppTool(self.store, PolicyEngine())

    def tearDown(self):
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def test_explicit_language_forces_compose(self):
        class Brain:
            def __init__(self):
                self.prompts = []

            def reason(self, s, p, context=None):
                self.prompts.append(p)
                return "सुप्रभात! आपका दिन शुभ हो।"

        brain = Brain()
        self.tool.brain = brain
        with mock.patch(
            "tools.computer.whatsapp_tool.load_contacts",
            return_value={"rohit": "+919049923832"}), mock.patch(
            "tools.computer.whatsapp_tool.kit.sendwhatmsg_instantly"
        ) as send:
            result = self.tool.run(
                "whatsapp rohit saying good morning in hindi")
        send.assert_called_once()
        self.assertIn("HINDI", brain.prompts[0])
        # hindi text went out, not the literal english words
        self.assertNotIn('"good morning', result)
