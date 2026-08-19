import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from awareness.briefing import BriefingBuilder
from awareness.initiative import InitiativeEngine
from awareness.monitors import DiskMonitor, RepoMonitor
from awareness.scheduler import Scheduler
from events.bus import EventBus
from memory.store import MemoryStore
from policies.engine import PolicyEngine


class AwarenessTest(unittest.TestCase):
    def test_bus_thread_safe_emit(self):
        bus = EventBus()
        seen = []
        bus.subscribe(lambda e: seen.append(e.kind))
        bus.emit("monitor.disk", {"used_percent": 91})
        self.assertEqual(seen, ["monitor.disk"])

    def test_disk_monitor_alert(self):
        bus = EventBus()
        path = tempfile.gettempdir()
        monitor = DiskMonitor(bus, path=path, threshold_percent=0)
        result = monitor.run_check()
        self.assertIsNotNone(result)
        self.assertIn("used_percent", result)

    def test_disk_monitor_silent_when_healthy(self):
        bus = EventBus()
        path = tempfile.gettempdir()
        monitor = DiskMonitor(bus, path=path, threshold_percent=200)
        result = monitor.run_check()
        self.assertIsNone(result)

    def test_scheduler_runs_and_stops(self):
        bus = EventBus()
        scheduler = Scheduler(bus)
        hits = []
        class FakeMonitor:
            interval = 1
            def run_check(self):
                hits.append(1)
        scheduler.add_monitor(FakeMonitor())
        scheduler.start()
        import time
        time.sleep(0.5)
        scheduler.stop()
        self.assertGreaterEqual(len(hits), 1)

    def test_initiative_disk_error_acts(self):
        bus = EventBus()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = InitiativeEngine(bus, store, PolicyEngine())
            decision = engine.evaluate("disk", {"error": "disk full"})
            self.assertEqual(decision["decision"], "act")
            task = engine.act(decision)
            self.assertIsNotNone(task)
            pending = store.recent_pending_tasks()
            store.close()
            self.assertEqual(len(pending), 1)

    def test_briefing_lists_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.add_task("deploy server")
            builder = BriefingBuilder(store)
            text = builder.build()
            store.close()
            self.assertIn("deploy server", text)


if __name__ == "__main__":
    unittest.main()