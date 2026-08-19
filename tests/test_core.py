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


if __name__ == "__main__":
    unittest.main()