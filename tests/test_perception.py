import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from events.bus import EventBus
from perception.sensors import PerceptionHub, SystemSensor


class PerceptionTest(unittest.TestCase):
    def test_system_sensor_reads(self):
        hub = PerceptionHub(EventBus())
        readings = hub.sense_all()
        self.assertIn("system", readings)
        self.assertIn("os", readings["system"])

    def test_sense_by_name(self):
        hub = PerceptionHub(EventBus())
        data = hub.sense("system")
        self.assertIsNotNone(data)
        self.assertIn("disk_used_percent", data)

    def test_sense_unknown_returns_none(self):
        hub = PerceptionHub(EventBus())
        self.assertIsNone(hub.sense("nonexistent"))


if __name__ == "__main__":
    unittest.main()