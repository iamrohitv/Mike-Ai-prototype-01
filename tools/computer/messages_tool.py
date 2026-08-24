from policies.engine import Level
from tools.base import Tool
from tools.computer import message_providers as mp


class MessagesTool(Tool):
    name = "messages"
    description = "read new messages from gmail and whatsapp web"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        wants_mail = "mail" in lowered and any(
            w in lowered for w in ("unread", "new", "check", "read", "any"))
        wants_wa = "whatsapp" in lowered and any(
            w in lowered for w in ("unread", "new", "check", "read",
                                   "missed", "message"))
        general = any(p in lowered for p in (
            "new messages", "read my messages", "any messages",
            "check my messages", "unread messages", "social media"))
        return wants_mail or wants_wa or general

    def run(self, request):
        lowered = request.lower().strip()
        want_mail = any(k in lowered for k in (
            "mail", "all", "everything")) or \
            "messages" in lowered or "social" in lowered
        want_wa = any(k in lowered for k in (
            "whatsapp", "all", "everything")) or \
            "messages" in lowered or "social" in lowered
        if not want_mail and not want_wa:
            want_mail = want_wa = True  # generic ask -> check everything

        blocks = []
        if want_mail:
            blocks.append(self._block("GMAIL", mp.fetch_unread_emails()))
        if want_wa:
            blocks.append(self._block("WHATSAPP",
                                      mp.fetch_whatsapp_unreads()))
        return "\n".join(blocks)

    @staticmethod
    def _block(title, result):
        lines = [f"[{title}]"]
        if not result["ok"]:
            lines.append(f"- unavailable: {result['note']}")
            return "\n".join(lines)
        lines.append(f"- {result['note']}")
        if not result["items"]:
            lines.append("  - nothing unread")
        for title_, detail in result["items"]:
            lines.append(f"  - {title_}: {detail}")
        return "\n".join(lines)

    def verify(self, result):
        if "[GMAIL]" in result or "[WHATSAPP]" in result:
            return "verified: checked"
        return "failed"