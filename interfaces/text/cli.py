import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from memory.store import MemoryStore
from core.context.context import ConversationContext
from core.reasoning.brain import Brain
from core.planning.planner import format_plan, make_plan
from policies.engine import PolicyEngine
from tools.registry import build_tools
from monitoring.logger import get_logger
from security.paths import db_path
from security.env import ensure_env_template
from events.bus import EventBus
from awareness.briefing import BriefingBuilder


class Mike:
    def __init__(self):
        ensure_env_template()
        self.memory = MemoryStore(db_path())
        self.logger = get_logger()
        self.policies = PolicyEngine()
        self.tools = build_tools(self.memory, self.policies)
        self.context = ConversationContext(self.memory)
        self.brain = Brain(self.memory)
        self.pending_clear = None
        self.events = EventBus()
        self.briefings = BriefingBuilder(self.memory)
        self.awareness = None
        self.operations = None
        self.perception = None

    def load_perception(self):
        from perception.sensors import PerceptionHub, ScreenSensor, SystemSensor
        if self.perception is None:
            self.perception = PerceptionHub(self.events, sensors=[SystemSensor(), ScreenSensor()])
        return self.perception

    def load_operations(self):
        from operations.reports import ReportRunner
        if self.operations is None:
            self.operations = ReportRunner(self.memory, self.policies)
        return self.operations

    def enable_awareness(self, scheduler=None):
        from awareness.initiative import InitiativeEngine
        from awareness.scheduler import Scheduler
        from guardian.engine import GuardianEngine
        self.awareness = scheduler or Scheduler(self.events)
        self.initiative = InitiativeEngine(
            self.events, self.memory, self.policies, self.brain
        )
        self.guardian = GuardianEngine(self.events, self.memory)

        def on_monitor(event):
            if not event.kind.startswith("monitor."):
                return
            kind = event.kind.split(".", 1)[-1]
            self.initiative.evaluate(kind, event.payload)
            self.guardian.evaluate(kind, event.payload)

        self.events.subscribe(on_monitor)
        try:
            from awareness.monitors import HealthMonitor
            self.awareness.add_monitor(HealthMonitor(self.events, self.guardian))
        except Exception:  # noqa: BLE001
            pass
        self.awareness.start()
        return self.awareness

    def briefing(self):
        recent_mem = self.memory.recent_memories(limit=4)
        pending = self.memory.recent_pending_tasks(limit=4)
        if not recent_mem and not pending:
            return None
        parts = []
        if pending:
            parts.append("Pending tasks:")
            for t in pending:
                parts.append(f"  - {t['title']}")
        if recent_mem:
            parts.append("Things I remember:")
            for m in recent_mem:
                parts.append(f"  - {m['content']}")
        return "\n".join(parts)

    def _handle_approval(self, text):
        lowered = text.strip().lower()
        if lowered not in ("approve", "yes approve", "approve it", "deny", "no deny", "deny it", "cancel"):
            return None
        if not self.policies.pending_approvals:
            return None
        tool_name, payload = next(iter(self.policies.pending_approvals.items()))
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if tool is None:
            return "There is a pending action, but I can't find the tool for it."
        if lowered.startswith("deny") or lowered == "cancel":
            self.policies.deny(tool_name)
            self.memory.log_action(
                action=tool_name, reason="denied by Rohit", result="denied",
                verification="denied",
            )
            self.logger.info("DENIED: %s by Rohit", tool_name)
            return "Understood — I've cancelled that. Nothing was changed."
        self.policies.approve(tool_name)
        self.memory.log_action(
            action=tool_name, reason="approved by Rohit", result="approved",
            verification="approved",
        )
        self.logger.info("APPROVED: %s by Rohit", tool_name)
        if hasattr(tool, "approve_pending"):
            return tool.approve_pending(payload)
        return "Approved. That action is now allowed."

    def handle_clear(self, text):
        active = self.memory.active_memories(limit=50)
        if not active:
            return "There's nothing in my memory to clear right now."

        targets = self.brain.target_memories(text, active)
        if not targets:
            return (
                "I don't have context on exactly which memories you mean, "
                "so I'm guessing nothing clearly matches. Tell me more "
                "specifically what to forget."
            )
        by_id = {m["id"]: m for m in active}
        chosen = [by_id[i] for i in targets if i in by_id]
        self.pending_clear = targets

        if len(chosen) == 1:
            summary = f"\"{chosen[0]['content']}\""
        else:
            summary = "\n".join(
                f"  - {m['content']}" for m in chosen
            )
        self.logger.info(
            "CLEAR REQUEST: %s -> ids %s", text, targets
        )
        return (
            f"I'll park these in the corner of my brain and stop mentioning "
            f"them:\n{summary}\n\n"
            f"Say 'confirm' to clear, or tell me what to keep."
        )

    def confirm_clear(self):
        if not self.pending_clear:
            return "There's nothing pending to clear."
        targets = self.pending_clear
        self.pending_clear = None
        count = self.memory.archive_memories(targets)
        self.memory.log_action(
            action="clear_memory",
            reason="confirmed by Rohit",
            result=f"archived {count} memories",
            verification="verified: memories archived",
        )
        return (
            f"Done. I've parked {count} memories in the corner of my brain. "
            "I won't mention them anymore - but they're safely kept if you "
            "ever ask to bring one back."
        )

    def peek_corner(self):
        archived = self.memory.archived_memories(limit=20)
        if not archived:
            return "The corner is empty - nothing has been archived."
        lines = [f"- {m['content']}" for m in archived]
        return "In the corner of my brain:\n" + "\n".join(lines)

    @staticmethod
    def _is_briefing_request(text):
        lowered = (text or "").lower()
        return any(
            phrase in lowered
            for phrase in [
                "brief me",
                "daily briefing",
                "give me a briefing",
                "what's the situation",
                "whats the situation",
                "what's the status",
                "whats the status",
                "what should i focus on",
            ]
        )

    @staticmethod
    def _is_remote_link_request(text):
        lowered = (text or "").lower()
        return any(
            phrase in lowered
            for phrase in [
                "remote link",
                "phone link",
                "where can i reach you",
                "access from anywhere",
                "tailscale",
            ]
        )

    def _handle_remote_link(self):
        lines = []
        try:
            from interfaces.remote.tailnet import tailnet_url
            url = tailnet_url(port=8877)
        except Exception:  # noqa: BLE001
            url = None
        if url:
            lines.append(
                f"From anywhere in the world, open {url} on your phone "
                "(Tailscale connected)."
            )
        else:
            lines.append(
                "Remote-from-anywhere is off. Install Tailscale on this PC and "
                "your phone, sign into both, then ask me again."
            )
        try:
            from interfaces.remote.server import _lan_ip
            ip = _lan_ip()
            lines.append(f"On your home wifi, open http://{ip}:8877.")
        except Exception:  # noqa: BLE001
            pass
        return "\n".join(lines)

    @staticmethod
    def _is_operation_request(text):
        lowered = (text or "").lower()
        return any(
            phrase in lowered
            for phrase in [
                "run the daily report",
                "daily report",
                "run project report",
                "project report",
                "run task triage",
                "task triage",
                "run the routine",
                "routine operations",
                "run operations",
                "run reports",
                "compact memory",
                "compact my memory",
                "run compact",
            ]
        )

    def _handle_operation(self, text):
        lowered = (text or "").lower()
        name = None
        if "daily report" in lowered:
            name = "daily_report"
        elif "project report" in lowered:
            name = "project_report"
        elif "task triage" in lowered:
            name = "task_triage"
        elif "compact" in lowered:
            name = "compact"
        runner = self.load_operations()
        results = runner.run(name=name)
        if not results:
            return "I don't have a routine operation for that yet."
        reply = "\n\n".join(results)
        self.context.add_mike(reply)
        return reply

    @staticmethod
    def _is_perception_request(text):
        lowered = (text or "").lower()
        return any(
            phrase in lowered
            for phrase in [
                "what do you sense",
                "what do you see",
                "sensor readings",
                "read your sensors",
                "what are you aware of",
                "check your senses",
            ]
        )

    def _handle_perception(self):
        hub = self.load_perception()
        readings = hub.sense_all()
        lines = ["Current senses:"]
        for name, data in readings.items():
            detail = ", ".join(f"{k}={v}" for k, v in data.items())
            lines.append(f"- {name}: {detail}")
        reply = "\n".join(lines)
        self.context.add_mike(reply)
        return reply

    @staticmethod
    def _is_reminder_request(text):
        lowered = (text or "").lower()
        return (
            "remind me in" in lowered
            or "remind me at" in lowered
            or "set a reminder" in lowered
            or lowered.startswith("list reminders")
            or "upcoming reminders" in lowered
        )

    def _handle_reminder(self, text):
        from datetime import datetime, timedelta, timezone
        lowered = text.lower()
        if lowered.startswith("list reminders") or "upcoming reminders" in lowered:
            pending = self.memory.pending_reminders(limit=20)
            if not pending:
                return "No reminders are scheduled."
            lines = ["Upcoming reminders:"]
            for r in pending:
                due = datetime.fromisoformat(r["due_ts"])
                local = due.astimezone()
                lines.append(f"- {r['title']} (due {local.strftime('%H:%M %d %b')})")
            return "\n".join(lines)
        minutes = 0
        for token in lowered.split():
            if token.isdigit():
                minutes = int(token)
                break
        if "hour" in lowered:
            minutes = minutes * 60
        if "day" in lowered:
            minutes = minutes * 1440
        if not minutes:
            minutes = 5
        title = re.sub(r"(?i)^(remind me in \d+ (minute|hour|day)s? (to|that|about)|remind me at \S+ (to|that|about)|set a reminder (in )?\d+ (minute|hour|day)s? (to|that|about)|set a reminder to)\s*", "", text).strip()
        if not title:
            title = text
        due = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        self.memory.add_reminder(title, due.isoformat())
        self.memory.log_action(
            action="reminder",
            reason="user request",
            result=f"in {minutes} minutes: {title}",
            verification="scheduled",
        )
        return (
            f"Done — I'll remind you about '{title}' in {minutes} minute"
            + ("s" if minutes != 1 else "")
            + "."
        )

    @staticmethod
    def _is_help_request(text):
        lowered = (text or "").lower()
        return lowered in ("help", "help me", "what can you do", "what can you do?")

    def _handle_help(self):
        lines = [
            "Here's what I can do:",
            "  talk        - just talk to me, I remember everything",
            "  brief me    - daily status from my memory and tasks",
            "  reminders   - 'remind me in 10 minutes to <thing>'",
            "  tasks       - add / list / complete tasks",
            "  notes       - 'remember that <thing>'",
            "  files       - 'read the file <path>'",
            "  terminal    - 'run the command <cmd>' (mutating needs approval)",
            "  git         - status, log, diff, commit, push (mutating needs approval)",
            "  system      - OS, disk and machine status",
            "  screenshot  - 'take a screenshot'",
            "  apps        - 'open notepad', 'launch calculator', 'start chrome'",
            "  project     - 'check the project'",
            "  senses      - 'what do you sense'",
            "  reports     - 'run the daily report' / 'run task triage'",
            "  clear       - 'forget about <thing>' (safe, never deleted)",
            "  recall      - 'what was I working on'",
            "  remote      - 'remote link' shows phone access URLs",
            "  voice       - desktop app listens and speaks, wake with 'hey mike'",
        ]
        return "\n".join(lines)

    def handle(self, text):
        self.context.add_user(text)
        self.logger.info("USER: %s", text)
        self.memory.record_metric("messages", 1)

        if self._is_help_request(text):
            reply = self._handle_help()
            self.context.add_mike(reply)
            return reply

        if self._is_briefing_request(text):
            reply = self.briefings.build()
            self.context.add_mike(reply)
            return reply

        if self._is_remote_link_request(text):
            reply = self._handle_remote_link()
            self.context.add_mike(reply)
            return reply

        if self._is_operation_request(text):
            return self._handle_operation(text)

        if self._is_perception_request(text):
            return self._handle_perception()

        if self._is_reminder_request(text):
            return self._handle_reminder(text)

        if self.pending_clear and text.strip().lower() in ("confirm", "yes clear"):
            return self.confirm_clear()

        if self.context.is_clear_request(text):
            return self.handle_clear(text)

        if self.context.is_peek_request(text):
            return self.peek_corner()

        approval_reply = self._handle_approval(text)
        if approval_reply is not None:
            return approval_reply

        if self.context.is_recall_request(text):
            context_blob = self.context.recall_context()
            system_prompt = self.context.system_prompt()
            answer = self.brain.reason(system_prompt, text, context=context_blob)
            self.context.add_mike(answer)
            self.logger.info("MIKE: %s", answer)
            return answer

        matched_tool = None
        for tool in self.tools:
            if tool.matches(text):
                matched_tool = tool
                break

        if matched_tool is None:
            selected = self.brain.select_tool(text, self.tools)
            if selected is not None:
                matched_tool = selected

        if matched_tool is not None:
            tool = matched_tool
            if self.policies.may_execute(tool.name):
                plan = make_plan(text, self.tools)
                self.logger.info("PLAN:\n%s", format_plan(plan))
                result = tool.run(text)
                verification = tool.verify(result)
                self.memory.log_action(
                    action=tool.name,
                    reason="matched user request",
                    result=result,
                    verification=verification,
                )
                self.context.add_mike(result)
                self.logger.info("MIKE: %s", result)
                return result
            else:
                self.logger.info("DENIED: %s requires higher authority", tool.name)
                return (
                    f"That action ({tool.name}) needs higher authority, "
                    "so I'm not executing it without your approval."
                )

        memory_context = self.context.relevant_context(text)
        if memory_context:
            context_blob = memory_context
        else:
            context_blob = None

        recent_talk = self.context.unsuppressed_talk(limit=6)
        if recent_talk:
            talk_lines = [
                f"{'Rohit' if role == 'user' else 'Mike'}: {content}"
                for role, content in recent_talk
            ]
            talk_blob = "Recent conversation:\n" + "\n".join(talk_lines)
            context_blob = (
                f"{context_blob}\n\n{talk_blob}" if context_blob else talk_blob
            )

        system_prompt = self.context.system_prompt()
        answer = self.brain.reason(system_prompt, text, context=context_blob)
        self.context.add_mike(answer)
        self.logger.info("MIKE: %s", answer)
        return answer


def main():
    mike = Mike()
    print("Mike is here. What would you like to discuss? (type 'exit' to leave)")
    briefing = mike.briefing()
    if briefing:
        print("\nHere's where things stand:")
        print(briefing)
        print()
    while True:
        try:
            line = input("you > ")
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            break
        if not line.strip():
            continue
        if line.strip().lower() in ("exit", "quit"):
            print("bye, Rohit.")
            break
        print(f"mike > {mike.handle(line.strip())}")


if __name__ == "__main__":
    sys.exit(main())