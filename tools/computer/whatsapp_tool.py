import re
import pywhatkit as kit
from policies.engine import Level
from tools.base import Tool


class WhatsAppTool(Tool):
    name = "whatsapp"
    description = "send whatsapp messages to contacts"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "whatsapp",
                "send message",
                "send msg",
                "text ",
            ]
        )

    def run(self, request):
        lowered = request.lower().strip()

        # Patterns: "send message to <contact> saying <msg>" / "whatsapp <contact> <msg>"
        # Extract contact and message
        contact = ""
        message = ""

        # Pattern 1: "send message to <contact> saying <msg>"
        match = re.search(
            r"(?:send\s+(?:message|msg)\s+to\s+|whatsapp\s+)([^:]+?)\s+(?:saying|that|:)\s+(.+)",
            lowered
        )
        if match:
            contact = match.group(1).strip()
            message = match.group(2).strip()
        else:
            # Pattern 2: "send <msg> to <contact> on whatsapp"
            match = re.search(
                r"(?:send\s+)(.+?)\s+to\s+(\S.+?)\s+(?:on\s+)?(?:whatsapp|wa)\b",
                lowered
            )
            if match:
                message = match.group(1).strip()
                contact = match.group(2).strip()
            else:
                # Pattern 3: "whatsapp <contact> <message>"
                match = re.search(
                    r"whatsapp\s+(\S+)\s+(.+)",
                    lowered
                )
                if match:
                    contact = match.group(1).strip()
                    message = match.group(2).strip()
                else:
                    return "Usage: 'send message to <contact> saying <message>' or 'whatsapp <contact> <message>'"

        if not contact or not message:
            return "Could not understand contact or message."

        # Resolve contact name to phone number
        phone = self._resolve_contact(contact)
        if not phone:
            return f"Unknown contact: {contact}. Add to contacts first."

        # Send via pywhatkit
        try:
            kit.sendwhatmsg_instantly(phone, message, wait_time=15, tab_close=True)
            return f"Sent WhatsApp message to {contact} ({phone})"
        except Exception as exc:
            return f"Failed to send message: {exc}"

    def _resolve_contact(self, contact):
        """Map contact name to phone number. Extend this dict with your contacts."""
        contacts = {
            "mom": "+91XXXXXXXXXX",
            "dad": "+91XXXXXXXXXX",
            "brother": "+91XXXXXXXXXX",
            "sister": "+91XXXXXXXXXX",
            "friend": "+91XXXXXXXXXX",
            # Add your contacts here: "name": "+91XXXXXXXXXX"
        }
        return contacts.get(contact.lower())

    def verify(self, result):
        if "Sent WhatsApp" in result:
            return "verified: message sent"
        if "Failed" in result or "Unknown contact" in result or "Usage" in result:
            return "failed"
        return "completed"