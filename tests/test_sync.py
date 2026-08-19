import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore


class SyncTest(unittest.TestCase):
    def test_register_and_list_devices(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.register_device("laptop", kind="laptop")
            store.register_device("phone", kind="phone")
            devices = store.list_devices()
            store.close()
            self.assertEqual(len(devices), 2)
            self.assertEqual(devices[0]["name"], "laptop")

    def test_sync_changes_since_ts(self):
        import time
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            store.remember("shared fact across devices")
            store.add_conversation("user", "hello sync")
            time.sleep(0.01)
            since = store._now()
            time.sleep(0.01)
            store.remember("added after baseline")
            changes = store.sync_changes(since_ts=since)
            store.close()
            self.assertEqual(len(changes["memories"]), 1)
            self.assertIn("added after baseline", changes["memories"][0]["content"])

    def test_apply_sync_dedupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(os.path.join(tmp, "m.db"))
            payload = {
                "memories": [
                    {"content": "remote fact", "kind": "fact",
                     "source": "sync", "status": "active", "ts": store._now()},
                ],
                "conversations": [],
            }
            store.apply_sync(payload, "phone")
            store.apply_sync(payload, "phone")
            changes = store.sync_changes()
            store.close()
            contents = [m["content"] for m in changes["memories"]]
            self.assertEqual(contents.count("remote fact"), 1)


if __name__ == "__main__":
    unittest.main()