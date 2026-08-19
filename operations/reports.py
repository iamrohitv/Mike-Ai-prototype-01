import subprocess
from datetime import datetime, timedelta, timezone


class Operation:
    name = "base"
    description = ""
    category = "routine"

    def __init__(self, memory, policies):
        self.memory = memory
        self.policies = policies

    def run(self):
        raise NotImplementedError


class DailyReportOperation(Operation):
    name = "daily_report"
    description = "produce a daily status report"
    category = "reporting"

    def run(self):
        pending = self.memory.recent_pending_tasks(limit=20)
        actions = self.memory.recent_actions(limit=10)
        now = datetime.now(timezone.utc)
        day_start = (now - timedelta(hours=now.hour)).isoformat()
        today_actions = [
            a for a in actions if a["ts"] >= day_start
        ]
        lines = [
            f"Daily report {now.strftime('%Y-%m-%d')}",
            f"Pending tasks: {len(pending)}",
            f"Actions today: {len(today_actions)}",
        ]
        if pending:
            lines.append("Open items:")
            for t in pending[:5]:
                lines.append(f"- {t['title']}")
        self.memory.remember(
            f"daily report generated with {len(pending)} pending tasks",
            kind="report",
            source="operation",
        )
        return "\n".join(lines)


class ProjectReportOperation(Operation):
    name = "project_report"
    description = "check the repo and summarize what changed"
    category = "reporting"

    def run(self):
        try:
            status = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True, text=True, timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "Project report unavailable (git failed)."
        if status.returncode != 0:
            return "Project report unavailable (not a git repo here)."
        changes = [l for l in status.stdout.splitlines() if l.strip()]
        if not changes:
            return "Project report: working tree is clean."
        summary = f"Project report: {len(changes)} items changed:\n"
        summary += "\n".join(changes[:15])
        self.memory.remember(
            f"project has {len(changes)} uncommitted changes",
            kind="report",
            source="operation",
        )
        return summary


class TaskTriageOperation(Operation):
    name = "task_triage"
    description = "review pending tasks and flag stale ones"
    category = "planning"

    def run(self):
        pending = self.memory.recent_pending_tasks(limit=100)
        stale = [t for t in pending if t["ts"] < (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()]
        if not stale:
            return "Task triage: no stale tasks."
        flagged = "\n".join(f"- {t['title']}" for t in stale[:5])
        self.memory.add_task("review stale tasks flagged by triage")
        return f"Task triage: {len(stale)} task(s) older than 7 days:\n{flagged}"


class CompactOperation(Operation):
    name = "compact"
    description = "fold old conversation into a summary and prune"
    category = "maintenance"

    def run(self):
        count = self.memory.conversation_count()
        if count <= 40:
            return f"Compact: conversation is small ({count} lines), nothing to fold."
        summarized = self.memory.summarize_old_conversation()
        pruned = self.memory.prune_conversations(keep=40)
        return (
            f"Compact: folded {summarized or 0} old lines into memory, "
            f"pruned {pruned} raw lines. {count} -> ~40 kept."
        )


class ReportRunner:
    def __init__(self, memory, policies):
        self.memory = memory
        self.policies = policies
        self.operations = [
            DailyReportOperation(memory, policies),
            ProjectReportOperation(memory, policies),
            TaskTriageOperation(memory, policies),
            CompactOperation(memory, policies),
        ]

    def run(self, name=None):
        targets = self.operations if name is None else [
            o for o in self.operations if o.name == name
        ]
        if not targets:
            return None
        results = []
        for op in targets:
            result = op.run()
            self.memory.log_action(
                action=f"operation.{op.name}",
                reason="autonomous routine run",
                result=result,
                verification="completed",
            )
            results.append(result)
        return results