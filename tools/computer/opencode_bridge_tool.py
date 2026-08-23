import re

import requests
from policies.engine import Level
from tools.base import Tool
from tools.computer.locations import (
    extract_location, looks_like_location_answer,
)

FILE_INTENT_RE = re.compile(
    r"\b(create|make|new|build|writ)\w*\b[^.]*?\b"
    r"(file|files|script|app|module|component|project|tool)\b", re.I)
PATH_HINT_RE = re.compile(
    r"[\\/]|[a-z]:\b|\b(desktop|documents|downloads|pictures?|folder|drive)\b",
    re.I)


class OpencodeBridgeTool(Tool):
    name = "opencode"
    description = "send a coding task to opencode via the bridge"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)
        self.bridge_url = "http://127.0.0.1:8765/bridge/command"
        self._pending_task = None

    def matches(self, request):
        if self._pending_task is not None:
            return True
        return "opencode" in request.lower()

    def run(self, request):
        lowered = request.lower().strip()

        # resume pending task once user names a destination
        if self._pending_task is not None:
            if looks_like_location_answer(request):
                loc = extract_location(lowered)
                base = loc[1] if loc else request.strip().strip('"')
                task = (
                    f"Create any new files inside '{base}'. "
                    + self._pending_task
                )
                self._pending_task = None
                return self._dispatch(task)
            # not a location: treat as a brand-new command
            self._pending_task = None

        # Extract the actual task
        task = request
        for trigger in ("opencode", "code this", "write code", "fix this", "refactor", "implement"):
            if lowered.startswith(trigger):
                task = request[len(trigger):].strip()
                break

        if not task:
            return "What would you like opencode to do?"

        if (FILE_INTENT_RE.search(task) and not PATH_HINT_RE.search(task)):
            self._pending_task = task
            return (
                "Where should opencode put the new files? Say 'on desktop', "
                "'in documents', an <X> drive, or a full folder path."
            )

        return self._dispatch(task)

    def _dispatch(self, task):
        try:
            response = requests.post(
                self.bridge_url,
                json={"command": task, "id": f"mike_{int(__import__('time').time())}"},
                timeout=640,
            )
            data = response.json()
            if response.status_code == 202 or data.get("status") == "busy":
                return "opencode is still busy with the previous task. Give it a minute, then try again."
            if "result" in data:
                return f"opencode: {data['result']}"
            return f"opencode error: {data.get('error', 'unknown')}"
        except requests.exceptions.Timeout:
            return (
                "opencode took longer than 10 minutes. It may still finish — "
                "ask me again in a bit and I'll check."
            )
        except requests.exceptions.ConnectionError:
            return "opencode bridge not running. Start with: python tools/computer/opencode_bridge.py"
        except Exception as exc:
            return f"opencode error: {exc}"

    def verify(self, result):
        if "opencode:" in result:
            return "verified: opencode executed"
        if "error" in result.lower():
            return "failed"
        return "completed"