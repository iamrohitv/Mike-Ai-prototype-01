import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from memory.store import MemoryStore
from core.context.context import ConversationContext
from core.reasoning.brain import Brain
from core.planning.planner import make_plan
from policies.engine import PolicyEngine
from tools.registry import build_tools
from monitoring.logger import get_logger
from security.paths import db_path
from security.env import ensure_env_template


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

    def handle(self, text):
        self.context.add_user(text)
        self.logger.info("USER: %s", text)

        if self.pending_clear and text.strip().lower() in ("confirm", "yes clear"):
            return self.confirm_clear()

        if self.context.is_clear_request(text):
            return self.handle_clear(text)

        if self.context.is_peek_request(text):
            return self.peek_corner()

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
                self.logger.info("PLAN: %s", " -> ".join(plan))
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