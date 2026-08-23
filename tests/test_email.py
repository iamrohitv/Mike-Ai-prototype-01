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


class OfferLetterFlowTest(unittest.TestCase):
    """Rohit's exact failing scenario: intent + inline 'his email is X'."""

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

    COMMAND = (
        "send mail to rohit giving a offer letter to join me as a "
        "co-founder in my tech company his email is "
        "officialvermarohit14@gmail.com"
    )

    def test_inline_address_detected(self):
        class FakeBrain:
            def reason(self, s, p, context=None):
                assert "co-founder" in p or "offer letter" in p
                return ("SUBJECT: Co-Founder Offer\n"
                        "BODY: Join me in my tech company. Regards, Rohit")

        self.tool.brain = FakeBrain()
        with mock.patch(
            "tools.computer.email_tool.smtplib.SMTP_SSL"
        ) as smtp:
            result = self.tool.run(self.COMMAND)
        self.assertTrue(result.startswith("Sent email"))
        sendmail_args = (smtp.return_value.__enter__.return_value
                         .sendmail.call_args[0])
        self.assertEqual(sendmail_args[1],
                         ["officialvermarohit14@gmail.com"])

    def test_missing_recipient_asks_then_answer_completes(self):
        class FakeBrain:
            def reason(self, s, p, context=None):
                return ("SUBJECT: Offer\nBODY: Join me as co-founder. "
                        "Regards, Rohit")

        # no address anywhere -> must ask and stash
        result = self.tool.run(
            "send mail giving an offer letter to join me as co-founder")
        self.assertIn("going to", result)
        self.assertIsNotNone(self.tool._pending_email)

        # bare address reply completes the whole send
        self.tool.brain = FakeBrain()
        with mock.patch(
            "tools.computer.email_tool.smtplib.SMTP_SSL"
        ) as smtp:
            second = self.tool.run("officialvermarohit14@gmail.com")
        self.assertTrue(second.startswith("Sent email"))
        sendmail_args = (smtp.return_value.__enter__.return_value
                         .sendmail.call_args[0])
        self.assertEqual(sendmail_args[1],
                         ["officialvermarohit14@gmail.com"])

    def test_send_him_the_mail_uses_last_recipient(self):
        self.tool._last_recipient = "officialvermarohit14@gmail.com"

        class FakeBrain:
            def reason(self, s, p, context=None):
                return "SUBJECT: Hi\nBODY: Sending it now."

        self.tool.brain = FakeBrain()
        with mock.patch(
            "tools.computer.email_tool.smtplib.SMTP_SSL"
        ) as smtp:
            result = self.tool.run("send him the mail about the offer")
        self.assertTrue(result.startswith("Sent email"))
        sendmail_args = (smtp.return_value.__enter__.return_value
                         .sendmail.call_args[0])
        self.assertEqual(sendmail_args[1],
                         ["officialvermarohit14@gmail.com"])


    def test_address_anywhere_beats_name_guess(self):
        """Rohit's exact second phrasing: 'to rohit for offering him... his
        email address is X' must resolve X, never 'be my cofunder'."""
        class FakeBrain:
            def reason(self, s, p, context=None):
                return "SUBJECT: Co-Founder Invite\nBODY: Join me!"

        self.tool.brain = FakeBrain()
        with mock.patch(
            "tools.computer.email_tool.smtplib.SMTP_SSL"
        ) as smtp:
            result = self.tool.run(
                "send a mail to rohit for offering him to be my cofunder on "
                "my tech company his email address is "
                "officialvermarohit14@gmail.com")
        self.assertTrue(result.startswith("Sent email"))
        self.assertNotIn("cofunder'", result)
        sendmail_args = (smtp.return_value.__enter__.return_value
                         .sendmail.call_args[0])
        self.assertEqual(sendmail_args[1],
                         ["officialvermarohit14@gmail.com"])


if __name__ == "__main__":
    unittest.main()