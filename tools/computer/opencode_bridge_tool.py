import requests
from policies.engine import Level
from tools.base import Tool


class OpencodeBridgeTool(Tool):
    name = "opencode"
    description = "send a coding task to opencode via the bridge"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)
        self.bridge_url = "http://127.0.0.1:8765/bridge/command"

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "opencode",
                "code this",
                "write code",
                "fix this",
                "refactor",
                "implement",
            ]
        )

    def run(self, request):
        lowered = request.lower().strip()
        
        # Extract the actual task
        task = request
        for trigger in ("opencode", "code this", "write code", "fix this", "refactor", "implement"):
            if lowered.startswith(trigger):
                task = request[len(trigger):].strip()
                break
        
        if not task:
            return "What would you like opencode to do?"
        
        try:
            response = requests.post(
                self.bridge_url,
                json={"command": task, "id": f"mike_{int(__import__('time').time())}"},
                timeout=130,
            )
            data = response.json()
            if "result" in data:
                return f"opencode: {data['result']}"
            return f"opencode error: {data.get('error', 'unknown')}"
        except requests.exceptions.Timeout:
            return "opencode: request timed out"
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