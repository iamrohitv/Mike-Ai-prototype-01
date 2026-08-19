import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from awareness.monitors import MetricMonitor, ReminderMonitor
from events.bus import EventBus
from memory.store import MemoryStore


class ReminderTest(unittest.TestCase):
    def test_add_and_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            due = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
            store.add_reminder("deploy server", due)
            pending = store.pending_reminders()
            store.close()
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["title"], "deploy server")

    def test_due_reminders_fires(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            due = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
            store.add_reminder("call client", due)
            monitor = ReminderMonitor(EventBus(), store)
            result = monitor.check()
            store.close()
            self.assertIsNotNone(result)
            self.assertIn("call client", result["due"])

    def test_future_reminder_not_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
            store.add_reminder("tomorrow task", due)
            monitor = ReminderMonitor(EventBus(), store)
            result = monitor.check()
            store.close()
            self.assertIsNone(result)

    def test_reminder_becomes_task_when_due(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            due = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
            store.add_reminder("pay invoice", due)
            monitor = ReminderMonitor(EventBus(), store)
            monitor.check()
            tasks = store.recent_pending_tasks()
            store.close()
            self.assertTrue(any("pay invoice" in t["title"] for t in tasks))


class MetricTest(unittest.TestCase):
    def test_record_and_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.record_metric("pending_tasks", 3)
            store.record_metric("pending_tasks", 5)
            recent = store.recent_metrics("pending_tasks")
            store.close()
            self.assertEqual(len(recent), 2)
            self.assertEqual(recent[0]["value"], 5)

    def test_metric_monitor_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.add_task("something to do")
            monitor = MetricMonitor(EventBus(), store)
            result = monitor.check()
            recent = store.recent_metrics("pending_tasks")
            store.close()
            self.assertEqual(result["pending_tasks"], 1)
            self.assertEqual(len(recent), 1)


if __name__ == "__main__":
    unittest.main()