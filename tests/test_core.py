import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.mood.mood import Mood, detect_mood
from memory.store import MemoryStore
from policies.engine import Level, PolicyEngine


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


class PolicyTest(unittest.TestCase):
    def test_authority_levels(self):
        engine = PolicyEngine()
        engine.allow("note", Level.GREEN)
        self.assertTrue(engine.may_execute("note"))
        self.assertFalse(engine.may_execute("unregistered"))


if __name__ == "__main__":
    unittest.main()