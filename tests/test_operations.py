import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from operations.reports import (
    CompactOperation, DailyReportOperation, ReportRunner, TaskTriageOperation,
)
from policies.engine import PolicyEngine


class OperationsTest(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        store = MemoryStore(os.path.join(tmp.name, "m.db"))
        policies = PolicyEngine()
        return tmp, store, policies

    def test_daily_report_generates(self):
        tmp, store, policies = self._setup()
        op = DailyReportOperation(store, policies)
        result = op.run()
        store.close()
        tmp.cleanup()
        self.assertIn("Daily report", result)

    def test_task_triage_no_stale(self):
        tmp, store, policies = self._setup()
        op = TaskTriageOperation(store, policies)
        result = op.run()
        store.close()
        tmp.cleanup()
        self.assertIn("no stale", result)

    def test_runner_logs_actions(self):
        tmp, store, policies = self._setup()
        runner = ReportRunner(store, policies)
        results = runner.run(name="daily_report")
        actions = store.recent_actions()
        store.close()
        tmp.cleanup()
        self.assertEqual(len(results), 1)
        self.assertTrue(any(a["action"] == "operation.daily_report" for a in actions))

    def test_compact_small_conversation_skips(self):
        tmp, store, policies = self._setup()
        op = CompactOperation(store, policies)
        result = op.run()
        store.close()
        tmp.cleanup()
        self.assertIn("nothing to fold", result)

    def test_compact_prunes_old_lines(self):
        tmp, store, policies = self._setup()
        for i in range(60):
            store.add_conversation("user", f"old line number {i}")
        op = CompactOperation(store, policies)
        result = op.run()
        count = store.conversation_count()
        store.close()
        tmp.cleanup()
        self.assertIn("Compact:", result)
        self.assertLessEqual(count, 40)


if __name__ == "__main__":
    unittest.main()