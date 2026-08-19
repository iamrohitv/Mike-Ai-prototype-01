import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mood.mood import Mood, detect_mood
from memory.store import MemoryStore
from policies.engine import Level, PolicyEngine
from tools.computer.terminal_tool import TerminalTool
from tools.computer.git_tool import GitTool
from tools.computer.system_tool import SystemTool
from tools.computer.screenshot_tool import ScreenshotTool
from tools.registry import build_tools


class MoodTest(unittest.TestCase):
    def test_low_detected(self):
        self.assertEqual(detect_mood("i'm tired, can't focus today"), Mood.LOW)

    def test_business_detected(self):
        self.assertEqual(detect_mood("client deadline is urgent"), Mood.BUSINESS)

    def test_normal_default(self):
        self.assertEqual(detect_mood("what's the plan for today"), Mood.NORMAL)


class MemoryTest(unittest.TestCase):
    def test_remember_and_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("Rohit is building the billing module")
            results = store.recall(query="billing")
            store.close()
            self.assertEqual(len(results), 1)
            self.assertIn("billing", results[0]["content"])

    def test_recall_falls_back_to_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("working on the client website redesign")
            results = store.recall(query="what was i working on")
            store.close()
            self.assertGreaterEqual(len(results), 1)

    def test_recall_word_overlap(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("finishing the billing module")
            store.remember("planning a vacation to goa")
            results = store.recall(query="billing module progress")
            store.close()
            self.assertIn("billing", results[0]["content"])

    def test_recall_prefers_biword_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("client alpha wants the dashboard module")
            store.remember("the billing module needs attention")
            store.remember("dashboard color scheme decision")
            results = store.recall(query="dashboard module")
            store.close()
            self.assertIn("dashboard module", results[0]["content"])

    def test_remember_auto_tags(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("deploy the billing module to production server")
            tagged = store.recall_by_tag("billing")
            store.close()
            self.assertTrue(any("billing" in m["content"] for m in tagged))

    def test_pending_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.add_task("deploy the server")
            tasks = store.recent_pending_tasks()
            store.close()
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["status"], "pending")

    def test_archive_hides_from_recall(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("the billing module for client X")
            store.remember("planning a vacation to goa")
            billing_id = next(
                m["id"]
                for m in store.active_memories()
                if "billing" in m["content"]
            )
            store.archive_memories([billing_id])
            results = store.recall(query="billing")
            store.close()
            contents = " ".join(r["content"] for r in results)
            self.assertNotIn("billing", contents)

    def test_archived_stays_in_corner(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("secret project details")
            active = store.active_memories()
            store.archive_memories([active[0]["id"]])
            archived = store.archived_memories()
            store.close()
            self.assertEqual(len(archived), 1)
            self.assertIn("secret project", archived[0]["content"])

    def test_restore_brings_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("important client preference")
            active = store.active_memories()
            store.archive_memories([active[0]["id"]])
            archived = store.archived_memories()
            store.restore_memories([archived[0]["id"]])
            results = store.recall(query="client preference")
            store.close()
            self.assertEqual(len(results), 1)


class PolicyTest(unittest.TestCase):
    def test_authority_levels(self):
        engine = PolicyEngine()
        engine.allow("note", Level.GREEN)
        self.assertTrue(engine.may_execute("note"))
        self.assertFalse(engine.may_execute("unregistered"))

    def test_needs_approval_orange(self):
        engine = PolicyEngine()
        engine.allow("terminal", Level.ORANGE)
        self.assertTrue(engine.needs_approval("terminal"))
        self.assertFalse(engine.may_execute("terminal"))


class ToolsTest(unittest.TestCase):
    def _engine(self):
        engine = PolicyEngine()
        engine.allow("terminal", Level.GREEN)
        engine.allow("git", Level.YELLOW)
        engine.allow("system", Level.GREEN)
        return engine

    def test_terminal_safe_command_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            tool = TerminalTool(store, self._engine())
            result = tool.run("run the command echo hello-world-test")
            store.close()
            self.assertIn("hello-world-test", result)

    def test_terminal_risky_requires_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = self._engine()
            tool = TerminalTool(store, engine)
            result = tool.run("run the command del important_file.txt")
            self.assertIn("approval", result)
            self.assertTrue(engine.needs_approval("terminal"))
            store.close()

    def test_system_tool_reports_machine(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            tool = SystemTool(store, self._engine())
            result = tool.run("system status")
            store.close()
            self.assertIn("OS:", result)
            self.assertIn("Disk:", result)

    def test_git_tool_requests_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = self._engine()
            tool = GitTool(store, engine)
            result = tool.run("commit and push")
            self.assertIn("approval", result)
            store.close()

    def test_screenshot_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            tool = ScreenshotTool(store, self._engine())
            self.assertTrue(tool.matches("take a screenshot please"))
            store.close()

    def test_build_tools_registers_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = PolicyEngine()
            tools = build_tools(store, engine)
            names = {t.name for t in tools}
            store.close()
            self.assertIn("terminal", names)
            self.assertIn("git", names)
            self.assertIn("system", names)
            self.assertIn("screenshot", names)
            self.assertIn("note", names)
            self.assertIn("task", names)
            self.assertIn("file", names)
            self.assertIn("project", names)


if __name__ == "__main__":
    unittest.main()