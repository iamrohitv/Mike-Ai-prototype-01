from tools.base import Tool
from policies.engine import Level


class NoteTool(Tool):
    name = "note"
    description = "remember a fact or note from Rohit"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "remember that",
                "note that",
                "remember this",
                "make a note",
                "note down",
                "don't forget",
                "do not forget",
            ]
        )

    def run(self, request):
        content = request.strip()
        self.memory.remember(content, kind="fact", source="note")
        return "Noted. I've remembered that."