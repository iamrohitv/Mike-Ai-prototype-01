import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.computer.whatsapp_tool import WhatsAppTool


class FakeBrain:
    def __init__(self, reply="Happy birthday! Have a great one, buddy."):
        self.reply = reply
        self.calls = []

    def reason(self, system, prompt, context=None):
        self.calls.append(prompt)
        return self.reply


class WhatsAppComposeTest(unittest.TestCase):
    def setUp(self):
        tmp = __import__("tempfile").TemporaryDirectory()
        self.tmp = tmp
        store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.store = store
        self.tool = WhatsAppTool(store, PolicyEngine())

    def tearDown(self):
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def _send(self, **kwargs):
        with mock.patch(
            "tools.computer.whatsapp_tool.kit.sendwhatmsg_instantly"
        ) as send:
            result = self.tool._send_resolved(**kwargs)
        return result, send

    def test_intent_uses_brain_composition(self):
        brain = FakeBrain("Wishing you a very happy birthday!")
        self.tool.brain = brain
        result, send = self._send(
            contact="rahul sharma",
            message="wish him happy birthday",
            phone="+919876543210",
        )
        self.assertIn("very happy birthday", result)
        self.assertEqual(len(brain.calls), 1)
        send.assert_called_once()

    def test_feedback_always_shows_actual_text(self):
        brain = FakeBrain("Get well soon!")
        self.tool.brain = brain
        result, _ = self._send(
            contact="rohit", message="feel better", phone="+919049923832",
        )
        self.assertRegex(result, r'Sent WhatsApp message to .+: ".+"')

    def test_verbatim_skips_brain(self):
        brain = FakeBrain()
        self.tool.brain = brain
        result, send = self._send(
            contact="mom", message="on my way", phone="+919812345678",
            verbatim=True,
        )
        self.assertIn('"on my way"', result)
        self.assertEqual(len(brain.calls), 0)
        send.assert_called_once_with(
            "+919812345678", "on my way", wait_time=15, tab_close=True
        )

    def test_brain_crash_never_sends(self):
        """Any brain error = inform in chat, send NOTHING (AGENTS.md rule)."""
        class DeadBrain:
            def reason(self, *a, **k):
                raise RuntimeError("offline")

        self.tool.brain = DeadBrain()
        result, send = self._send(
            contact="dad", message="call me back", phone="+919899999999",
        )
        self.assertIn("did NOT send", result)
        send.assert_not_called()

    def test_brain_offline_text_is_never_sent(self):
        """Brain's fallback string must not go out as a real message."""
        class OfflineBrain:
            def reason(self, *a, **k):
                return ("I don't have context on this, so I'm guessing: "
                        "I can't reach my brain right now.")

        self.tool.brain = OfflineBrain()
        result, send = self._send(
            contact="rohit", message="", phone="+919049923832",
        )
        self.assertIn("did NOT send", result)
        send.assert_not_called()  # nothing went out

    # ---- regression: user-reported failures -------------------------- #

    @mock.patch("tools.computer.whatsapp_tool.load_contacts",
                return_value={"rohit": "+919049923832"})
    def test_saying_plus_draft_word_composes(self, _book):
        """'saying and drafting a condolence...' must COMPOSE, not send junk."""
        brain = FakeBrain("Deepest condolences on your loss.")
        self.tool.brain = brain
        self.tool._resolve_contact = lambda name: "+919049923832"
        with mock.patch(
            "tools.computer.whatsapp_tool.kit.sendwhatmsg_instantly"
        ) as send:
            result = self.tool.run(
                "send message to rohit saying and drafting a condolence "
                "for death of his pet"
            )
        self.assertIn("condolence", result.lower())
        self.assertEqual(len(brain.calls), 1)  # composed, not verbatim
        sent_text = send.call_args[0][1]
        self.assertNotIn("drafting", sent_text.lower())

    @mock.patch("tools.computer.whatsapp_tool.load_contacts",
                return_value={"rohit": "+919049923832"})
    def test_pronoun_him_uses_last_contact(self, _book):
        """'whatsapp him this message' after talking about rohit -> rohit."""
        brain = FakeBrain("Sorry for your loss, thinking of you.")
        self.tool.brain = brain
        self.tool._last_contact = "rohit"
        self.tool._resolve_contact = lambda name: (
            "+919049923832" if name == "rohit" else None
        )
        with mock.patch(
            "tools.computer.whatsapp_tool.kit.sendwhatmsg_instantly"
        ) as send:
            result = self.tool.run("whatsapp him this message")
        self.assertIn("rohit", result)
        self.assertEqual(send.call_args[0][0], "+919049923832")

    @mock.patch("tools.computer.whatsapp_tool.load_contacts",
                return_value={"rohit": "+919049923832"})
    def test_scaffold_draft_and_whatsapp_resolves_contact(self, _book):
        """'Draft a message to Rohit ... and WhatsApp him' must not Usage-error."""
        brain = FakeBrain("Heartfelt condolences on your pet.")
        self.tool.brain = brain
        self.tool._resolve_contact = lambda name: (
            "+919049923832" if "rohit" in name.lower() else None
        )
        with mock.patch(
            "tools.computer.whatsapp_tool.kit.sendwhatmsg_instantly"
        ) as send:
            result = self.tool.run(
                "draft a message to rohit giving my condolence on death of "
                "his pet and whatsapp him"
            )
        self.assertTrue(result.startswith("Sent WhatsApp message"))
        self.assertNotIn("Usage:", result)


if __name__ == "__main__":
    unittest.main()