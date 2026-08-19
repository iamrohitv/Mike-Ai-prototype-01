import re
import subprocess

from policies.engine import Level
from tools.base import Tool


class GitTool(Tool):
    name = "git"
    description = "run git operations: status, log, commit, push, pull"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "git commit",
                "commit the changes",
                "commit and push",
                "git push",
                "git pull",
                "commit changes",
                "git status",
                "git log",
                "git add",
                "stage the",
                "git diff",
            ]
        )

    def _extract_commit_message(self, request):
        lowered = request.lower()
        for phrase in [
            "commit message",
            "commit with message",
            "commit as",
            "commit the changes as",
            "commit and push",
        ]:
            lowered = lowered.replace(phrase, "")
        lowered = re.sub(r"^(please |can you |could you |mike |hey )+", "", lowered)
        lowered = re.sub(r"\b(git commit|commit|git add|and push|push)\b", " ", lowered)
        lowered = " ".join(lowered.split())
        if '"' in lowered:
            lowered = lowered.split('"')[1] if lowered.count('"') >= 2 else lowered
        elif "'" in lowered:
            lowered = lowered.split("'")[1] if lowered.count("'") >= 2 else lowered
        return lowered.strip() or "update"

    def run(self, request):
        lowered = request.lower()

        if "status" in lowered:
            return self._git(["git", "status", "--short"])
        if "log" in lowered:
            return self._git(["git", "log", "--oneline", "-10"])
        if "diff" in lowered:
            return self._git(["git", "diff", "--stat"])
        if "pull" in lowered:
            return self._git(["git", "pull"])
        if "commit" in lowered or "push" in lowered:
            return self._commit_or_push(lowered, request)
        return "I can run status, log, diff, pull, commit, or push. Try something like 'commit and push'."

    def _commit_or_push(self, lowered, request):
        message = self._extract_commit_message(request)
        if "push" in lowered and "commit" in lowered:
            self.policies.require_approval(
                self.name, {"action": "commit and push", "message": message}
            )
            return (
                f"Committing and pushing as \"{message}\" needs your approval. "
                "Say 'approve' to proceed, or 'deny' to cancel."
            )
        if "commit" in lowered:
            self.policies.require_approval(
                self.name, {"action": "commit", "message": message}
            )
            return (
                f"Committing as \"{message}\" needs your approval. "
                "Say 'approve' to proceed, or 'deny' to cancel."
            )
        if "push" in lowered:
            self.policies.require_approval(
                self.name, {"action": "push", "message": message}
            )
            return (
                "Pushing needs your approval. Say 'approve' to proceed, "
                "or 'deny' to cancel."
            )
        return "unknown git operation"

    def approve_pending(self, payload=None):
        payload = payload or self.policies.pending_approvals.get(self.name)
        if not payload:
            return "There is no git operation waiting for approval."
        self.policies.approve(self.name)
        action = payload.get("action") if isinstance(payload, dict) else payload
        out = []
        if "commit" in action:
            message = payload.get("message", "update")
            status = self._git(["git", "status", "--short"])
            if "nothing to commit" in status or not status.strip():
                return "Working tree is clean — nothing to commit."
            self._git(["git", "add", "-A"])
            out.append(self._git(["git", "commit", "-m", message]))
        if "push" in action:
            out.append(self._git(["git", "push"]))
        return "\n".join(out) or "done"

    def _git(self, args):
        try:
            proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            return "Could not run git."
        result = (proc.stdout or "").strip()
        if not result and proc.stderr:
            result = proc.stderr.strip()
        if not result:
            return "(no output)"
        if len(result) > 4000:
            result = result[:4000] + "\n...[truncated]"
        return result

    def verify(self, result):
        if "approval" in result:
            return "pending approval"
        if "Could not" in result or "fatal" in result.lower():
            return "failed"
        return "verified: git operation succeeded"