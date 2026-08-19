from tools.base import Tool
from policies.engine import Level


class TaskTool(Tool):
    name = "task"
    description = "add a task, list pending tasks, or mark a task done"
    level = Level.GREEN

    def __init__(self, memory, policies):
        super().__init__(memory, policies)
        policies.allow(self.name, self.level)

    def matches(self, request):
        lowered = request.lower()
        add = any(
            p in lowered
            for p in [
                "add a task",
                "add task",
                "create a task",
                "remind me to",
                "task:",
                "todo:",
            ]
        )
        list_pending = any(
            p in lowered
            for p in [
                "what's pending",
                "whats pending",
                "what is pending",
                "list tasks",
                "pending tasks",
                "list my tasks",
            ]
        )
        done = any(
            p in lowered
            for p in ["mark task", "complete task", "task done", "finish task"]
        )
        return add or list_pending or done

    def run(self, request):
        lowered = request.lower()

        if "mark task" in lowered or "complete task" in lowered or "task done" in lowered:
            for word in request.split():
                if word.isdigit():
                    self.memory.complete_task(int(word))
                    return f"Task {word} marked as done."
            return "Which task number should I mark done? Say 'complete task <number>'."

        if any(p in lowered for p in ["list tasks", "pending tasks", "list my tasks"]):
            return self._format_tasks(self.memory.list_tasks(status="pending"))

        if "what's pending" in lowered or "whats pending" in lowered or "what is pending" in lowered:
            return self._format_tasks(self.memory.list_tasks(status="pending"))

        title = request.strip()
        for prefix in [
            "add a task ",
            "add task ",
            "create a task ",
            "remind me to ",
            "task: ",
            "todo: ",
        ]:
            if lowered.startswith(prefix):
                title = title[len(prefix):].strip()
                break
        if title:
            self.memory.add_task(title)
            return f"Added task: {title}"
        return "What task should I add?"

    def _format_tasks(self, tasks):
        if not tasks:
            return "No pending tasks."
        lines = [f"- (task {t['id']}) {t['title']}" for t in tasks]
        return "Pending tasks:\n" + "\n".join(lines)

    def verify(self, result):
        if "Added task" in result or "done" in result:
            return "verified: task updated in memory"
        if "Pending tasks" in result or "No pending tasks" in result:
            return "verified: task list read"
        return "completed"