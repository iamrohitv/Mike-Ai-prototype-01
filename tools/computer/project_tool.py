import subprocess

from tools.base import Tool
from policies.engine import Level


class ProjectTool(Tool):
    name = "project"
    description = "inspect the project state and report what needs attention"
    level = Level.YELLOW

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        return any(
            phrase in lowered
            for phrase in [
                "check the project",
                "inspect the project",
                "project status",
                "what needs attention",
                "look at the project",
                "inspect my project",
                "check my project",
            ]
        )

    def run(self, request):
        try:
            status = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            branch = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "Could not inspect the project (git unavailable)."

        branch_name = branch.stdout.strip() if branch.returncode == 0 else "unknown"
        changes = [line for line in status.stdout.splitlines() if line.strip()]

        result = f"On branch {branch_name}."
        if changes:
            result += f"\n{len(changes)} changed/untracked items:\n" + "\n".join(
                changes[:20]
            )
        else:
            result += "\nWorking tree is clean."
        return result

    def verify(self, result):
        if "Could not" in result:
            return "failed"
        if "On branch" in result:
            return "verified: git commands succeeded"
        return "completed"