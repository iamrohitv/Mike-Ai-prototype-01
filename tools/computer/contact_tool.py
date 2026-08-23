import re

from policies.engine import Level
from tools.base import Tool
from tools.computer.contacts import load_contacts, save_contact


SAVE_PATTERNS = [
    # save contact <name> as <value>  /  add email <value> as <name> ...
    re.compile(
        r"\b(save|add|append|store|remember)\s+(?:a\s+)?"
        r"(contact|number|email|mail)\s+(.+)", re.I),
]
NAME_AS_VALUE_RE = re.compile(
    r"^([a-z][a-z0-9 ]{0,24}?)\s*(?:as|is|=|:)\s+(\S+)$", re.I)
VALUE_AS_NAME_RE = re.compile(
    r"^\s*(\S+@\S+|\+?[\d][\d\s\-]{6,}\d)\s+(?:as|for|to|under)\s+"
    r"([a-z][a-z0-9 ]{0,24})$", re.I)
LIST_RE = re.compile(r"\b(show|list)\b.{0,20}\bcontacts?\b", re.I)


class ContactTool(Tool):
    name = "contacts"
    description = "save numbers/emails under a name for whatsapp & mail"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        if LIST_RE.search(lowered):
            return True
        if not re.search(r"\b(contact|number|email|mail)\b", lowered):
            return False
        return bool(re.search(r"\b(save|add|append|store|remember)\b", lowered))

    def run(self, request):
        lowered = request.lower().strip()

        if LIST_RE.search(lowered):
            return self._list()

        m = None
        for pat in SAVE_PATTERNS:
            m = pat.search(lowered)
            if m:
                break
        if not m:
            return ("Say things like: 'save number 9876543210 as mom' or "
                    "'add email boss@x.com as boss', or 'show contacts'.")

        kind_word, rest = m.group(2).lower(), m.group(3).strip()

        value_first = VALUE_AS_NAME_RE.match(rest)
        name_value = NAME_AS_VALUE_RE.match(rest)
        if kind_word in ("number", "email", "mail") and value_first:
            value, name = value_first.group(1), value_first.group(2)
        elif name_value:
            name, value = name_value.group(1), name_value.group(2)
        else:
            parts = rest.rsplit(None, 1)          # 'save contact mom 987...'
            if len(parts) != 2:
                return ("Give me both: e.g. 'save contact mom 9876543210' "
                        "or 'add email a@b.com as boss'.")
            name, value = parts[0].strip(" .,"), parts[1]

        if name.lower() in ("number", "email", "contact"):
            return "What name should I save it under?"

        kind, stored = save_contact(name, value)
        if kind is None:
            return (f"'{value}' doesn't look like a valid phone number "
                    "or email address.")

        label = "phone (whatsapp)" if kind == "phone" else "email"
        extra = ""
        if kind == "phone" and stored.startswith("+91") and \
                not re.sub(r"\D", "", str(value)).__len__() > 10 and \
                not str(value).strip().startswith("+"):
            extra = " (assumed +91 country code)"
        return f"Saved {name} -> {stored} [{label}]{extra}"

    def _list(self):
        book = load_contacts()
        if not book:
            return ("No contacts yet. Save some with: 'save number 9876543210 "
                    "as mom'.")
        lines = [f"- {k}: {v}" for k, v in sorted(book.items())]
        return f"{len(book)} contact(s):\n" + "\n".join(lines)

    def verify(self, result):
        if result.startswith("Saved ") or result.endswith("):"):
            return "verified: contact saved"
        if "doesn't look like" in result or "Give me both" in result or \
                "name should I save" in result:
            return "failed"
        return "completed"