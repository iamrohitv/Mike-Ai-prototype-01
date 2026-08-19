import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from events.bus import EventBus
from guardian.engine import GuardianEngine, GuardianLevel
from memory.store import MemoryStore

import unittest
from unittest import mock


class GuardianTest(unittest.TestCase):
    def test_normal_does_nothing(self):
        bus = EventBus()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = GuardianEngine(bus, store)
            level = engine.evaluate("monitor.disk", {"used_percent": 50})
            self.assertEqual(level, GuardianLevel.NORMAL)
            self.assertEqual(len(engine.recent_checkins()), 0)
            store.close()

    def test_unusual_triggers_checkin(self):
        bus = EventBus()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = GuardianEngine(bus, store)
            level = engine.evaluate("monitor.disk", {"used_percent": 92})
            self.assertEqual(level, GuardianLevel.UNUSUAL)
            self.assertEqual(len(engine.recent_checkins()), 1)
            pending = store.recent_pending_tasks()
            store.close()
            self.assertGreaterEqual(len(pending), 1)

    def test_emergency_escalates(self):
        bus = EventBus()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = GuardianEngine(bus, store)
            level = engine.evaluate("monitor.server", {"error": "disk full"})
            self.assertEqual(level, GuardianLevel.EMERGENCY)
            actions = store.recent_actions(limit=5)
            store.close()
            self.assertTrue(any(a["action"] == "guardian_emergency" for a in actions))

    def test_high_disk_is_emergency(self):
        bus = EventBus()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = GuardianEngine(bus, store)
            level = engine.evaluate("monitor.disk", {"used_percent": 99})
            self.assertEqual(level, GuardianLevel.EMERGENCY)
            store.close()

    def test_health_monitor_escalates_on_full_disk(self):
        from awareness.monitors import HealthMonitor

        bus = EventBus()
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            engine = GuardianEngine(bus, store)
            monitor = HealthMonitor(bus, engine)

            fake = mock.Mock()
            fake.cpu_percent.return_value = 30
            fake.virtual_memory.return_value.percent = 40
            fake.disk_usage.return_value.percent = 99.5
            fake.sensors_battery.return_value = None

            with mock.patch.dict("sys.modules", {"psutil": fake}):
                result = monitor.check()

            self.assertIsNotNone(result)
            self.assertEqual(result["level"], "emergency")
            store.close()


if __name__ == "__main__":
    unittest.main()