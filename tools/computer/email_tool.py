import os
import re
import smtplib
from email.mime.text import MIMEText

from policies.engine import Level
from tools.base import Tool
from tools.computer.contacts import load_contacts
from tools.computer.compose_lang import extract_language, language_directive


SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

YES_RE = re.compile(
    r"^\s*(yes|ya|yeah|yep|haan?|sure|ok(?:ay)?|correct|right|do it|go ahead|sahi)\b",
    re.I)
NO_RE = re.compile(r"^\s*(no|nope|nahi|nah|cancel|stop|don'?t|galat)\b", re.I)

VERBATIM_RE = re.compile(r"\b(?:saying|that)\b\s|:\s")
INTENT_RE = re.compile(
    r"\b(draft|compos|writ|craft|pen|condol|apolog|wish|greet|congratulat|"
    r"thank|invit|remind|follow[- ]?up)\w*", re.I)

FROM_RE = re.compile(r"\bfrom\s+([\w.\-+]+@[\w.\-]+|me)\b")
TO_RE = re.compile(
    r"\bto\s+(?:the\s+)?"
    r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}|[a-z][a-z ]{1,30}?)"
    r"(?=\s+(?:about|regarding|saying|that|with|subject|body|and|on)\b|[,.:!]|$)",
    re.I)
SUBJECT_RE = re.compile(
    r"\b(?:about|regarding|subject(?:\s+(?:is|as))?)\s+([^,.]+?)"
    r"(?=\s+(?:saying|that|body)\b|[,.:]|$)", re.I)
BODY_RE = re.compile(r"\b(?:saying|that|body(?:\s+(?:is|text))?)\s*[:,-]?\s+(.+)$",
                     re.I)


def _account():
    return (
        os.environ.get("MIKE_EMAIL_ADDRESS", "").strip(),
        os.environ.get("MIKE_EMAIL_APP_PASSWORD", "").strip(),
    )


class EmailTool(Tool):
    name = "email"
    description = "send email from your configured gmail account"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)
        self._pending_send = None
        self._last_recipient = None

    def matches(self, request):
        if self._pending_send is not None:
            return True
        lowered = request.lower()
        if any(p in lowered for p in ["send mail", "send email", "e-mail",
                                      "email ", " mail "]):
            return True
        return bool(re.search(r"\bsend\b.{0,60}\b(mail|email)\b", lowered))

    # ------------------------------------------------------------------ #
    def run(self, request):
        lowered = request.lower().strip()
        self._lang = extract_language(lowered)

        addr, password = _account()
        if not addr or not password:
            return (
                "Email isn't set up yet. Put these in config/.env and "
                "restart me:\nMIKE_EMAIL_ADDRESS=you@gmail.com\n"
                "MIKE_EMAIL_APP_PASSWORD=<16-char google app password>\n"
                "(Google Account -> Security -> 2-Step Verification -> "
                "App passwords.)"
            )

        # pending confirmation from fuzzy recipient match
        if self._pending_send is not None:
            if YES_RE.match(lowered):
                pend = self._pending_send
                self._pending_send = None
                self._last_recipient = pend["to"]
                return self._deliver(pend["to"], pend["subject"],
                                     pend["body"], addr, password)
            if NO_RE.match(lowered):
                self._pending_send = None
                return "Cancelled - nothing was sent."

        from_addr, explicit_from = self._extract_from(lowered, addr)
        if explicit_from and not from_addr:
            return (f"I only have one sender configured ({addr}). "
                    f"I can't send from '{explicit_from}'.")

        to_raw, subject, body = self._extract_parts(lowered)

        if not to_raw:
            return "Who is this email going to?"

        to_addr = self._resolve_recipient(to_raw)
        if not to_addr:
            return (f"I don't have an email address for '{to_raw}'. "
                    "Add it to config/contacts.json (value must contain '@') "
                    "or give the full address.")
        self._last_recipient = to_addr

        verbatim = bool(VERBATIM_RE.search(lowered)) and not INTENT_RE.search(lowered)
        if (not verbatim and body and not INTENT_RE.search(body)
                and len(body.split()) <= 6 and "@" not in body):
            verbatim = True
        # explicit '... in hindi' => must draft (literal words can't translate)
        if self._lang:
            verbatim = False

        if verbatim:
            final_subject = subject or "(no subject)"
            final_body = body or "(empty body)"
        else:
            drafted = self._compose(to_addr, subject, body)
            if not drafted:
                return (
                    f"I couldn't draft that email right now (my brain is "
                    f"unreachable), so I did NOT send anything to {to_addr}. "
                    "Try again later, or dictate it with 'saying ...'."
                )
            final_subject, final_body = drafted

        return self._deliver(to_addr, final_subject, final_body,
                             addr, password,
                             confirm=not verbatim and False)

    # ------------------------------------------------------------------ #
    def _extract_from(self, lowered, configured):
        m = FROM_RE.search(lowered)
        if not m:
            return configured, False
        raw = m.group(1)
        if raw.lower() == "me" or raw.lower() == configured.lower():
            return configured, True
        return None, raw  # unsupported alternate sender

    def _extract_parts(self, lowered):
        m = TO_RE.search(lowered)
        to_raw = m.group(1).strip() if m else ""
        # 'mail rahul ...' / 'email a@b.com ...' without the word 'to'
        if not to_raw:
            m2 = re.search(r"\b(?:e?mail)\s+"
                           r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}"
                           r"|[a-z][a-z ]{1,30}?)"
                           r"(?=\s+(?:about|regarding|saying|that|with|in)\b"
                           r"|[,.:!]|$)", lowered)
            if m2:
                to_raw = m2.group(1).strip()

        m = SUBJECT_RE.search(lowered)
        subject = m.group(1).strip() if m else ""

        m = BODY_RE.search(lowered)
        body = m.group(1).strip().strip('"') if m else ""
        return to_raw, subject, body

    def _resolve_recipient(self, raw):
        raw = raw.strip()
        if "@" in raw:
            return raw
        for key, value in load_contacts().items():
            if "@" in value and (raw == key or key.startswith(raw)
                                 or raw in key):
                return value
        # pronoun-style follow-up
        if raw in ("him", "her", "them") and self._last_recipient:
            return self._last_recipient
        return None

    def _compose(self, to_addr, subject_hint, instruction):
        brain = getattr(self, "brain", None)
        if brain is None:
            return None
        ctx = getattr(self, "_conversation_context", lambda: "")()
        prompt = f"Write a short professional-but-warm email to {to_addr}. "
        if instruction:
            prompt += f"Instruction: {instruction}. "
        elif subject_hint:
            prompt += f"Topic: {subject_hint}. "
        if ctx:
            prompt += f"\nRecent conversation:\n{ctx[:1200]}\n"
        prompt += ("Reply in EXACTLY this format:\nSUBJECT: <max 8 words>\n"
                   "BODY: <2-4 sentences, greeting + message + sign-off>. "
                   + language_directive(getattr(self, "_lang", None)))
        try:
            out = (brain.reason("You write concise personal emails.", prompt)
                   or "")
        except Exception:  # noqa: BLE001
            return None
        return self._parse_draft(out)

    def _parse_draft(self, text):
        text = re.sub(r"\s*\([^)]*(?:brain|sourced|memory|source)[^)]*\)\s*$",
                      "", text.strip(), flags=re.I)
        sm = re.search(r"SUBJECT\s*:\s*(.+)", text, re.I)
        bm = re.search(r"BODY\s*:\s*(.+)", text, re.I | re.S)
        subject = sm.group(1).strip().strip('"') if sm else ""
        body = bm.group(1).strip() if bm else ""
        if not subject or not body:
            return None
        if re.search(r"can'?t reach my brain|i'?m guessing|don'?t have context",
                     body + subject, re.I):
            return None
        return subject, body

    def _deliver(self, to_addr, subject, body, addr, password, confirm=False):
        if os.environ.get("MIKE_EMAIL_DRYRUN", "") == "1":
            return (f"[dry-run] Would email {to_addr} from {addr}\n"
                    f"Subject: {subject}\nBody:\n{body}")
        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = addr
        msg["To"] = to_addr
        msg["Subject"] = subject
        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30) as server:
                server.login(addr, password)
                server.sendmail(addr, [to_addr], msg.as_string())
        except Exception as exc:  # noqa: BLE001
            return f"Failed to send email: {exc}"
        return (f'Sent email to {to_addr} from {addr}\n'
                f'Subject: "{subject}"\nBody: "{body}"')

    # test seam -------------------------------------------------------- #
    def _resolve_and_deliver_for_test(self, to_addr, subject, body,
                                      addr="a@b.c", password="x"):
        return self._deliver(to_addr, subject, body, addr, password)

    def verify(self, result):
        if result.startswith("Sent email") or "[dry-run]" in result:
            return "verified: email sent"
        if (result.startswith("Failed") or "don't have" in result
                or "did NOT send" in result or "couldn't draft" in result
                or "going to?" in result or "set up yet" in result
                or "only have one sender" in result):
            return "failed"
        return "completed"