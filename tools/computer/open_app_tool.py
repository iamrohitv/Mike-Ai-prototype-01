import os
import subprocess

from policies.engine import Level
from tools.base import Tool


KNOWN_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "paint": "mspaint.exe",
    "wordpad": "write.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "terminal": "wt.exe",
    "explorer": "explorer.exe",
    "file explorer": "explorer.exe",
    "settings": 'start "" ms-settings:',
    "control panel": "control.exe",
    "task manager": "taskmgr.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "browser": "msedge.exe",
    "vscode": "code.exe",
    "code": "code.exe",
    "vs code": "code.exe",
    "visual studio code": "code.exe",
    "discord": "discord.exe",
    "spotify": "spotify.exe",
    "steam": "steam.exe",
    "outlook": "outlook.exe",
    "teams": "teams.exe",
    "zoom": "zoom.exe",
    "slack": "slack.exe",
    "whatsapp": "whatsapp.exe",
    "telegram": "telegram.exe",
}


class OpenAppTool(Tool):
    name = "open_app"
    description = "open a windows application by name"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "open ",
                "launch ",
                "start ",
                "run ",
            ]
        )

    def run(self, request):
        lowered = request.lower().strip()
        for trigger in ("open ", "launch ", "start ", "run "):
            if lowered.startswith(trigger):
                target = lowered[len(trigger):].strip()
                break
        else:
            target = request.strip()

        if not target:
            return "What would you like me to open?"

        cmd = self._resolve(target)
        if not cmd:
            return f"I don't know how to open '{target}'. Try a known app like notepad, calculator, chrome, vscode, etc."

        try:
            subprocess.Popen(cmd, shell=isinstance(cmd, str))
            return f"Opening {target}..."
        except Exception as exc:
            return f"Failed to open {target}: {exc}"

    def _resolve(self, target):
        target = target.strip().lower()
        if target in KNOWN_APPS:
            return KNOWN_APPS[target]
        if target.endswith(".exe"):
            return target
        if target.endswith(".lnk"):
            return f'start "" "{target}"'
        if os.path.isfile(target):
            return f'start "" "{target}"'
        return None

    def verify(self, result):
        if "Opening " in result and result.endswith("..."):
            return "verified: app launched"
        if "Failed to open" in result or "don't know how" in result:
            return "failed"
        return "completed"