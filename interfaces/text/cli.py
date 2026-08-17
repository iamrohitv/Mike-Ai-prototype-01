import sys

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

    def handle(self, text):
        self.context.add_user(text)
        self.logger.info("USER: %s", text)

        for tool in self.tools:
            if tool.matches(text):
                if self.policies.may_execute(tool.name):
                    plan = make_plan(text, self.tools)
                    self.logger.info("PLAN: %s", " -> ".join(plan))
                    result = tool.run(text)
                    self.memory.log_action(
                        action=tool.name,
                        reason="matched user request",
                        result=result,
                        verification="tool returned a result",
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

        memory_context = self.context.relevant_memory(text)
        if memory_context:
            context_blob = "\n".join(m["content"] for m in memory_context)
        else:
            context_blob = None

        system_prompt = self.context.system_prompt()
        answer = self.brain.reason(system_prompt, text, context=context_blob)
        self.context.add_mike(answer)
        self.logger.info("MIKE: %s", answer)
        return answer


def main():
    mike = Mike()
    print("Mike is here. What would you like to discuss? (type 'exit' to leave)")
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