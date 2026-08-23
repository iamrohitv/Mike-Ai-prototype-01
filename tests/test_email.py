import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.computer.email_tool import EmailTool, _account


class EmailToolTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.tmp = tmp
        self.store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.tool = EmailTool(self.store, PolicyEngine())
        self._old_env = dict(os.environ)
        os.environ["MIKE_EMAIL_ADDRESS"] = "rohit.test@gmail.com"
        os.environ["MIKE_EMAIL_APP_PASSWORD"] = "fakepass123"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._old_env)
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def test_not_configured_informs(self):
        os.environ.pop("MIKE_EMAIL_ADDRESS")
        result = self.tool.run("send mail to a@b.com saying hi")
        self.assertIn("Email isn't set up yet", result)

    @mock.patch("tools.computer.email_tool.load_contacts",
                return_value={"rahul": "rahul@gmail.com"})
    def test_verbatim_parse_and_send(self, _book):
        with mock.patch(
            "tools.computer.email_tool.smtplib.SMTP_SSL"
        ) as smtp:
            result = self.tool.run(
                "email rahul about project update saying here is the file"
            )
        self.assertTrue(result.startswith("Sent email"))
        self.assertIn("project update", result)
        msg = smtp.call_args[0][0] if smtp.call_args else None
        sendmail_args = smtp.return_value.__enter__.return_value \
            .sendmail.call_args[0]
        self.assertEqual(sendmail_args[1], ["rahul@gmail.com"])

    def test_from_mismatch_rejected(self):
        result = self.tool.run(
            "send mail from someone@else.com to a@b.com saying hi")
        self.assertIn("only have one sender", result)

    def test_from_me_accepted(self):
        with mock.patch("tools.computer.email_tool.smtplib.SMTP_SSL"):
            result = self.tool.run(
                "send mail from me to a@b.com saying hi")
        self.assertNotIn("only have one sender", result)

    @mock.patch("tools.computer.email_tool.load_contacts",
                return_value={"rahul": "rahul@gmail.com"})
    def test_brain_fail_never_sends(self, _book):
        class DeadBrain:
            def reason(self, *a, **k):
                raise RuntimeError("offline")

        self.tool.brain = DeadBrain()
        with mock.patch(
            "tools.computer.email_tool.smtplib.SMTP_SSL"
        ) as smtp:
            result = self.tool.run(
                "email rahul about apologies saying drafting an apology")
        self.assertIn("did NOT send", result)
        if smtp.call_args:
            smtp.return_value.__enter__.return_value.sendmail\
                .assert_not_called()

    @mock.patch("tools.computer.email_tool.load_contacts",
                return_value={"rahul": "rahul@gmail.com"})
    def test_dry_run(self, _book):
        os.environ["MIKE_EMAIL_DRYRUN"] = "1"
        try:
            result = self.tool.run(
                "email rahul about hi saying hello there friend")
            self.assertIn("[dry-run]", result)
        finally:
            os.environ.pop("MIKE_EMAIL_DRYRUN")

    def test_recipient_pronoun_uses_last(self):
        self.tool._last_recipient = "rahul@gmail.com"
        with mock.patch("tools.computer.email_tool.smtplib.SMTP_SSL"):
            result = self.tool.run(
                "send email to him about status saying all good")
        self.assertIn("rahul@gmail.com", result)


if __name__ == "__main__":
    unittest.main()