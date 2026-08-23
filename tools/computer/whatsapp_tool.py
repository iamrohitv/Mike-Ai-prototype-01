import os
import re
import pywhatkit as kit
from policies.engine import Level
from tools.base import Tool
from tools.computer.contacts import load_contacts, resolve_detailed, is_raw_number
from tools.computer.compose_lang import extract_language, language_directive


DRY_RUN = os.environ.get("MIKE_WHATSAPP_DRYRUN", "") == "1"

# "saying X" / ": X" -> send X word-for-word (unless intent verbs present)
VERBATIM_RE = re.compile(r"\b(?:saying|that)\b\s|:\s")
# instruction words mean Mike should draft it himself, even if 'saying' appears
INTENT_RE = re.compile(
    r"\b(draft|compos|writ|craft|pen|word|condol|apolog|wish|greet|"
    r"congratulat|thank|invit|remind)\w*",
    re.I,
)
PRONOUNS = {"him", "her", "them", "that person", "the person"}
THIS_MESSAGE = {"this message", "that message", "it", "the message", ""}

YES_RE = re.compile(
    r"^\s*(yes|ya|yeah|yep|yaas|haan?|ha\s+bhai|sure|ok(?:ay)?|correct|right|"
    r"do it|send (?:it|him|her)|go ahead|sahi)\b", re.I)
NO_RE = re.compile(r"^\s*(no|nope|nahi|nah|cancel|stop|don'?t|galat)\b", re.I)

# brain-offline fallback text must NEVER be treated as a drafted message
BRAIN_FAIL_RE = re.compile(
    r"(can'?t reach my brain|i'?m guessing|don'?t have context|"
    r"local brain|global key|brain is (?:offline|unreachable))",
    re.I,
)


class WhatsAppTool(Tool):
    name = "whatsapp"
    description = "send whatsapp messages to contacts"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)
        self._last_contact = None
        self._pending_send = None

    def matches(self, request):
        if self._pending_send is not None:
            return True
        lowered = request.lower()
        # email commands belong to EmailTool - never hijack them
        if re.search(r"\be-?mail\b|\bmail\b", lowered) and \
                "whatsapp" not in lowered:
            return False
        if any(p in lowered for p in ["whatsapp", "send message", "send msg", "text "]):
            return True
        # generic shapes: 'send hi to rohit', 'draft a msg ... whatsapp him'
        generic = bool(re.search(r"\bsend\b.{0,60}\bto\b", lowered))
        scaffold = bool(re.search(
            r"\b(draft|compos|writ)\w*\b.*\bwhatsapp\b|"
            r"\bwhatsapp\b.*\b(draft|compos|writ)\w*\b", lowered))
        return generic or scaffold

    def run(self, request):
        lowered = request.lower().strip()
        self._lang = extract_language(lowered)

        # pending confirmation from a fuzzy name match ('rhit' -> 'rohit')
        if self._pending_send is not None:
            if YES_RE.match(lowered):
                pend = self._pending_send
                self._pending_send = None
                self._last_contact = pend["contact"]
                return self._send_resolved(
                    pend["contact"], pend["message"], pend["phone"],
                    verbatim=pend["verbatim"],
                )
            if NO_RE.match(lowered):
                self._pending_send = None
                return "Cancelled - nothing was sent."
            # not a yes/no: fall through and treat as a fresh command

        contact, message = self._extract(lowered)

        # --- contact fallbacks -------------------------------------------
        if not contact or contact.strip() in PRONOUNS:
            known = self._find_known_contact(lowered)
            contact = known or self._last_contact or contact
        elif not self._resolve_contact(contact) and not is_raw_number(contact):
            known = self._find_known_contact(lowered)
            if known:
                contact = known

        if not contact:
            return (
                "Who should I send this to? I couldn't tell from your message."
            )

        # resolve with typo-awareness: fuzzy hits ask before sending
        if is_raw_number(contact):
            phone, fuzzy = contact.strip(), False
        else:
            phone, matched_key, fuzzy = resolve_detailed(
                contact, load_contacts())
            if not phone and not fuzzy:
                known = self._find_known_contact(lowered)
                if known and not self._pending_send:
                    num, key, fz = resolve_detailed(known, load_contacts())
                    if num:
                        contact, phone, fuzzy = known, num, fz
        if not phone:
            return (
                f"I don't have a number for '{contact}'. Export your contacts "
                "from contacts.google.com as vCard to config/contacts.vcf "
                "(or add them to config/contacts.json), then try again."
            )

        self._last_contact = contact  # remember for pronoun follow-ups

        # --- message fallbacks -------------------------------------------
        if message.strip().lower() in THIS_MESSAGE:
            message = ""  # pure intent - compose from conversation context

        verbatim = bool(VERBATIM_RE.search(lowered)) and not INTENT_RE.search(
            lowered
        )
        # short literal content ('send hi to rhit') is word-for-word too -
        # only prose instructions get drafted by the brain
        if (not verbatim and message and not INTENT_RE.search(message)
                and len(message.split()) <= 5):
            verbatim = True
        # explicit '... in hindi' means draft it - literal words can't translate
        if self._lang:
            verbatim = False

        if fuzzy and not self._pending_send:
            self._pending_send = {
                "contact": matched_key or contact,
                "phone": phone,
                "message": message,
                "verbatim": verbatim,
            }
            return (
                f"Closest contact I know is '{matched_key}' ({phone}). "
                "Send it there? Say yes / no."
            )

        return self._send_resolved(contact, message, phone, verbatim=verbatim)

    # ------------------------------------------------------------------ #
    def _extract(self, lowered):
        """Return (contact, message) from known command shapes."""
        # raw number target first (numbers may contain spaces/dashes)
        m = re.search(
            r"(?:whatsapp|send\s+(?:message|msg)\s+to)\s+"
            r"(\+?\d[\d\s\-()]{6,}\d)\s+(.+)",
            lowered,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        m = re.search(
            r"(?:send\s+(?:message|msg)\s+to\s+|whatsapp\s+)([^:]+?)\s+"
            r"(?:saying|that|:)\s+(.+)",
            lowered,
        )
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # 'send hi to rohit' / 'send greetings to mom'
        m = re.search(r"\bsend\s+([^:]*?)\s+to\s+([a-z][a-z ]{1,30}?)(?:\s+on\s+whatsapp|\s*$)", lowered)
        if m:
            return m.group(2).strip(), m.group(1).strip()

        m = re.search(r"(?:send\s+)(.+?)\s+to\s+(\S.+?)\s+(?:on\s+)?(?:whatsapp|wa)\b", lowered)
        if m:
            return m.group(2).strip(), m.group(1).strip()

        m = re.search(r"whatsapp\s+(\S+)\s+(.+)", lowered)
        if m:
            return m.group(1).strip(), m.group(2).strip()

        # scaffold: "draft/compose/write ... to <name> ... whatsapp ..."
        m = re.search(
            r"\b(?:draft|compos\w*|writ\w*)\b[^.]*?\b(?:to|for)\s+([a-z][a-z ]{1,30}?)"
            r"\s*(?:and|then|,|\.|$).*\bwhatsapp\b",
            lowered,
        )
        if not m:
            m = re.search(
                r"\bwhatsapp\b.*?\b(?:to|for)\s+([a-z][a-z ]{1,30}?)\s*(?:and|then|,|\.|$)",
                lowered,
            )
        if m:
            name = m.group(1).strip()
            for stop in ("and", "then", "via", "on"):
                idx = name.find(f" {stop} ")
                if idx != -1:
                    name = name[:idx]
            return name.strip(), ""

        return "", ""

    def _find_known_contact(self, text):
        """Scan the request for any name already in the contacts book."""
        try:
            book = load_contacts()
        except Exception:  # noqa: BLE001
            return None
        best, best_len = None, 0
        for key in book:
            for token in key.split():
                if len(token) >= 3 and re.search(
                    rf"\b{re.escape(token)}\b", text
                ):
                    if len(key) > best_len:
                        best, best_len = key, len(key)
                    break
        return best

    def _resolve_contact(self, contact):
        num, _key, _fuzzy = resolve_detailed(contact)
        return num

    def _conversation_context(self):
        try:
            from core.context.context import ConversationContext
            return ConversationContext(self.memory).recall_context()
        except Exception:  # noqa: BLE001
            return ""

    def _compose(self, contact, instruction):
        """Draft a short WhatsApp message from an instruction via the brain."""
        brain = getattr(self, "brain", None)
        if brain is None:
            return None
        ctx = self._conversation_context()
        prompt = (
            f"Write a short, natural WhatsApp message from Rohit to {contact}. "
        )
        if instruction:
            prompt += f"Instruction: {instruction}. "
        else:
            prompt += (
                "Use the recent conversation below to decide what the message "
                "should say (e.g. a draft that was just discussed). "
            )
        if ctx:
            prompt += f"\nRecent conversation:\n{ctx[:1500]}\n"
        prompt += (
            "Reply with ONLY the message text - no quotes, no explanations, "
            "no signature, max 3 sentences. "
            + language_directive(getattr(self, "_lang", None))
        )
        try:
            drafted = (brain.reason(
                "You write brief personal WhatsApp messages.", prompt
            ) or "").strip().strip('"').strip()
        except Exception:  # noqa: BLE001
            return None
        prev = None
        while prev != drafted:
            prev = drafted
            drafted = re.sub(
                r"\s*\([^)]*(?:brain|sourced|memory|source|context)[^)]*\)\s*$",
                "", drafted.strip(), flags=re.I,
            ).strip()
        drafted = drafted.strip('"').strip()
        if not drafted or BRAIN_FAIL_RE.search(drafted):
            return None  # compose failed - caller must NOT send anything
        return drafted

    def _send_resolved(self, contact, message, phone, verbatim=False):
        sent_text = message
        if not verbatim:
            composed = self._compose(contact, message)
            if composed:
                sent_text = composed
            else:
                return (
                    f"I couldn't draft that message right now (my brain is "
                    f"unreachable), so I did NOT send anything to {contact}. "
                    "Try again in a bit, or give me the exact words with "
                    "'saying ...' and I'll send those word-for-word."
                )
        if not sent_text or not sent_text.strip():
            return (f"I ended up with an empty message for {contact}, so I "
                    "did NOT send anything. Tell me what to say.")

        if DRY_RUN:
            return (
                f"[dry-run] Would send WhatsApp message to {contact} ({phone}): "
                f"'{sent_text}'"
            )
        try:
            kit.sendwhatmsg_instantly(phone, sent_text, wait_time=15, tab_close=True)
        except Exception as exc:
            return f"Failed to send message: {exc}"
        return f'Sent WhatsApp message to {contact} ({phone}): "{sent_text}"'

    def verify(self, result):
        if "Sent WhatsApp" in result or "[dry-run]" in result:
            return "verified: message sent"
        if ("Failed" in result or "don't have a number" in result
                or "couldn't tell" in result or "did NOT send" in result
                or "couldn't draft" in result):
            return "failed"
        return "completed"