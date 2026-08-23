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
    r"(?=\s+(?:about|regarding|saying|that|with|subject|body|and|on|in|at|"
    r"for|his|her|by|as|is|so|because|but|he|she|they|giving)\b|[,.:!]|$)",
    re.I)
EMAIL_RE = re.compile(r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})", re.I)
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
        self._pending_email = None
        self._last_recipient = None

    def matches(self, request):
        lowered = request.lower().strip()
        # 'save/add email ...' belongs to the contacts manager
        if re.match(r"\s*(?:save|add|append|store|remember)\b", lowered):
            return False
        if self._pending_send is not None or self._pending_email is not None:
            return True
        if any(p in lowered for p in ["send mail", "send email", "e-mail",
                                      "email ", " mail "]):
            return True
        if re.search(r"\bsend\b.{0,40}\b(him|her|them)\b.{0,30}\b(e?mail)\b",
                     lowered):
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

        # pending recipient: user is answering our 'who is this going to?'
        if self._pending_email is not None:
            candidate = lowered.strip().strip(",.")
            resolved = self._resolve_recipient(candidate)
            if resolved:
                pend = self._pending_email
                self._pending_email = None
                self._last_recipient = resolved
                return self._finish_send(resolved, pend, addr, password,
                                         request)
            if YES_RE.match(lowered) or NO_RE.match(lowered):
                self._pending_email = None
                return "Okay, dropped that email. Tell me the full command again."
            # not an address -> treat as a brand-new command below
            self._pending_email = None

        from_addr, explicit_from = self._extract_from(lowered, addr)
        if explicit_from and not from_addr:
            return (f"I only have one sender configured ({addr}). "
                    f"I can't send from '{explicit_from}'.")

        to_raw, subject, body = self._extract_parts(lowered)

        if not to_raw:
            pronoun = re.search(r"\b(him|her|them)\b", lowered)
            if pronoun:
                to_raw = pronoun.group(1)
            elif "@" in lowered:
                any_addr = re.search(
                    r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})", lowered)
                if any_addr:
                    to_raw = any_addr.group(1)

        if not to_raw:
            # stash the composed parts and ask; next reply completes it
            self._pending_email = {"subject": subject, "body": body,
                                   "instruction": self._clean_instruction(lowered)}
            return (
                "Who is this email going to? Give me the address, a contact "
                "name, or say 'him/her' if we mentioned them earlier."
            )

        to_addr = self._resolve_recipient(to_raw)
        if not to_addr:
            return (f"I don't have an email address for '{to_raw}'. "
                    "Add it to config/contacts.json (value must contain '@') "
                    "or give the full address.")
        self._last_recipient = to_addr

        return self._finish_send(
            to_addr,
            {"subject": subject, "body": body,
             "instruction": self._clean_instruction(lowered)},
            addr, password, lowered,
        )

    def _clean_instruction(self, lowered):
        """Rough intent text: strip command scaffolding for the composer."""
        text = re.sub(r"\b(?:send|draft|write|compose)\b.*?\b(?:e?mail)\b",
                      "", lowered)
        text = re.sub(r"\bfrom\s+\S+", "", text)
        text = re.sub(r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,})", "", text)
        text = re.sub(r"\b(?:his|her|their)\s+email\s+is\b", "", text)
        text = re.sub(r"\bto\s+(?:the\s+)?[a-z][a-z ]{0,30}", "", text, count=1)
        text = re.sub(r"\s+(?:in\s+hindi|in\s+hinglish|in\s+english)\b", "", text)
        return text.strip(" ,.:") or ""

    def _finish_send(self, to_addr, parts, addr, password, lowered):
        subject = parts.get("subject", "")
        body = parts.get("body", "")

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
            instruction = parts.get("instruction", "")
            drafted = self._compose(to_addr, subject, body or instruction)
            if not drafted:
                return (
                    f"I couldn't draft that email right now (my brain is "
                    f"unreachable), so I did NOT send anything to {to_addr}. "
                    "Try again later, or dictate it with 'saying ...'."
                )
            final_subject, final_body = drafted

        return self._deliver(to_addr, final_subject, final_body,
                             addr, password)

    # ------------------------------------------------------------------ #
    def _extract_from(self, lowered, configured):
        m = FROM_RE.search(lowered)
        if not m:
            return configured, False
        raw = m.group(1)
        if raw.lower() == "me" or raw.lower() == configured.lower():
            return configured, True
        return None, raw  # unsupported alternate sender

    INTENT_VERBS_RE = re.compile(
        r"^(join|offer|draft|writ\w*|give|sendl?|create|make|build|discuss|"
        r"share|ask|tell|inform|invit\w*|wish|thank|apolog\w*|say)\b", re.I)

    def _extract_parts(self, lowered):
        # address-anywhere wins: 'his email address is X', trailing emails etc.
        any_addr = EMAIL_RE.search(lowered)
        if any_addr:
            to_raw = any_addr.group(1)
        else:
            m = TO_RE.search(lowered)
            to_raw = m.group(1).strip() if m else ""
            # 'to join me' / 'to offer him' = purpose clause, not a person
            if to_raw and self.INTENT_VERBS_RE.match(to_raw):
                to_raw = ""
        # 'mail rahul ...' / 'email a@b.com ...' without the word 'to'
        if not to_raw:
            m2 = re.search(r"\b(?:e?mail)\s+"
                           r"([a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}"
                           r"|[a-z][a-z ]{1,30}?)"
                           r"(?=\s+(?:about|regarding|saying|that|with|in)\b"
                           r"|[,.,:!]|$)", lowered)
            if m2:
                cand = m2.group(1).strip()
                # 'send him the MAIL about x' -> capture is the object phrase,
                # not a recipient; discard junk captures
                if not re.match(r"(?:about|regarding|with|that|saying)\b",
                                cand):
                    to_raw = cand

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
                   "Always sign off with 'Rohit' - NEVER placeholders like "
                   "[Your Name]. Avoid ALL-CAPS words and links. "
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