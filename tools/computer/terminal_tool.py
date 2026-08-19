import os
import re
import subprocess

from policies.engine import Level
from tools.base import Tool

SAFE_PREFIXES = [
    "ls",
    "dir",
    "pwd",
    "whoami",
    "echo",
    "type",
    "cat",
    "find",
    "where",
    "git status",
    "git diff",
    "git log",
    "git branch",
    "python --version",
    "pip --version",
]

RISKY_MARKERS = [
    "rm ",
    "del ",
    "rd ",
    "rmdir ",
    "format ",
    "shutdown ",
    "taskkill ",
    "move ",
    "ren ",
    ">",
    "|",
    "&&",
    "||",
    ":;",
]

CONFIRM_MARKERS = [
    "git add",
    "git commit",
    "git push",
    "git reset",
    "git checkout",
    "git merge",
    "git rebase",
    "git stash",
    "pip install",
    "pip uninstall",
    "npm install",
    "npm run",
    "mkdir",
    "md ",
    "copy ",
    "xcopy ",
    "python -m unittest",
    "pytest",
]


class TerminalTool(Tool):
    name = "terminal"
    description = "run a terminal command on the machine"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "run the command",
                "run command",
                "execute this",
                "run this",
                "in the terminal",
                "terminal command",
                "run a command",
            ]
        )

    def _command(self, request):
        command = request
        for phrase in [
            "run the command",
            "run command",
            "execute this",
            "run this",
            "in the terminal",
            "terminal command",
            "run a command",
        ]:
            command = command.replace(phrase, "")
        command = re.sub(r"^(please|can you|could you|mike|hey)\s*", "", command.strip())
        return command.strip()

    def _classify(self, command):
        lowered = command.lower()
        for marker in RISKY_MARKERS:
            if marker in lowered:
                return Level.ORANGE
        for prefix in CONFIRM_MARKERS:
            if lowered.startswith(prefix):
                return Level.ORANGE
        for prefix in SAFE_PREFIXES:
            if lowered.startswith(prefix):
                return Level.GREEN
        return Level.YELLOW

    def run(self, request):
        command = self._command(request)
        if not command:
            return "Which command would you like me to run?"
        level = self._classify(command)
        self.policies.allow(f"{self.name}:{command[:40]}", level)
        self.policies.allow(self.name, level)

        if self.policies.needs_approval(self.name):
            self.policies.require_approval(self.name, {"command": command})
            return (
                f"That command ({command}) needs your approval before I run it. "
                "Say 'approve' to allow it, or 'deny' to cancel."
            )
        return self._execute(command)

    def _execute(self, command):
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            return "That command timed out after 60 seconds."
        except OSError as exc:
            return f"Could not run that command: {exc}"
        output = (proc.stdout or "").strip()
        error = (proc.stderr or "").strip()
        lines = []
        if proc.returncode != 0:
            lines.append(f"exit code {proc.returncode}")
        if output:
            lines.append(output)
        if error and error != output:
            lines.append(f"stderr: {error}")
        result = "\n".join(lines) if lines else "(no output)"
        if len(result) > 4000:
            result = result[:4000] + "\n...[truncated]"
        return result

    def verify(self, result):
        if "approval" in result or "Which command" in result:
            return "pending approval"
        if "Could not" in result or "timed out" in result:
            return "failed"
        return "verified: command executed"

    def approve_pending(self, payload=None):
        payload = payload or self.policies.pending_approvals.get(self.name)
        if not payload:
            return "There is no command waiting for approval."
        self.policies.approve(self.name)
        command = payload.get("command") if isinstance(payload, dict) else payload
        if not command:
            return "There is no command waiting for approval."
        return self._execute(command)