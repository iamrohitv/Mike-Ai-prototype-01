from datetime import datetime


class BriefingBuilder:
    def __init__(self, memory):
        self.memory = memory

    def build(self, monitor_alerts=None):
        monitor_alerts = monitor_alerts or {}
        parts = []

        hour = datetime.now().hour
        greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
        parts.append(f"{greeting}, Rohit. Here's what I know.")

        pending = self.memory.recent_pending_tasks(limit=10)
        if pending:
            parts.append(f"You have {len(pending)} pending task" + ("s." if len(pending) != 1 else "."))
            for t in pending[:5]:
                parts.append(f"- {t['title']}")

        recent = self.memory.recent_memories(limit=5)
        if recent:
            parts.append("From what I remember recently:")
            for m in recent:
                parts.append(f"- {m['content']}")

        if monitor_alerts:
            parts.append("Things that need attention:")
            for source, detail in monitor_alerts.items():
                parts.append(f"- {source}: {detail}")

        actions = self.memory.recent_actions(limit=5)
        if actions:
            parts.append("Last things I did:")
            for a in actions:
                parts.append(f"- {a['action']} ({a.get('verification') or 'done'})")

        if not pending and not recent and not monitor_alerts:
            parts.append("Nothing pending. You're clear to start fresh.")

        return "\n".join(parts)

    def short(self):
        pending = self.memory.recent_pending_tasks(limit=5)
        if not pending:
            return "No pending tasks."
        return f"{len(pending)} pending task" + ("s." if len(pending) != 1 else ".")