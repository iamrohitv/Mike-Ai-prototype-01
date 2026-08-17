import os

from tools.base import Tool
from policies.engine import Level


class FileTool(Tool):
    name = "file"
    description = "read a text file and summarize it"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in ["read the file", "open the file", "show me the file"]
        )

    def run(self, request):
        path = request.strip()
        path = path.replace("read the file", "").replace("open the file", "").strip()
        if not path:
            return "Which file would you like me to read?"
        if not os.path.isfile(path):
            return f"I couldn't find that file: {path}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            return f"Could not read {path}."
        preview = content[:1500]
        return f"{path} ({len(content)} chars):\n{preview}"