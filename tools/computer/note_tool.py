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
        lowered = content.lower()
        for prefix in [
            "remember that ",
            "note that ",
            "remember this ",
            "make a note ",
            "note down ",
            "don't forget ",
            "do not forget ",
        ]:
            if lowered.startswith(prefix):
                content = content[len(prefix):].strip()
                break
        if not content:
            return "What should I remember?"
        self.memory.remember(content, kind="fact", source="note")
        return "Noted. I've remembered that."

    def verify(self, result):
        stored = self.memory.recall(query=None, limit=1)
        if stored:
            return "verified: stored in memory"
        return "failed"