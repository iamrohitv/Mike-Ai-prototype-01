import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.computer import contacts as contacts_mod
from tools.computer.contact_tool import ContactTool


class ContactSaveTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.tmp = tmp
        self.json_path = os.path.join(tmp.name, "contacts.json")
        self.store = MemoryStore(os.path.join(tmp.name, "t.db"))
        self.tool = ContactTool(self.store, PolicyEngine())
        self._patches = [
            mock.patch.object(contacts_mod, "_json_path",
                              return_value=self.json_path),
            mock.patch("tools.computer.contact_tool.load_contacts",
                       side_effect=lambda: contacts_mod.load_json_contacts(
                           self.json_path)),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        try:
            self.store.close()
        finally:
            self.tmp.cleanup()

    def _saved(self):
        if not os.path.exists(self.json_path):
            return {}
        with open(self.json_path, encoding="utf-8") as f:
            return json.load(f)

    def test_save_number_name_first(self):
        result = self.tool.run("save contact mom 9876543210")
        self.assertIn("Saved mom", result)
        self.assertIn("+919876543210", result)
        self.assertEqual(self._saved()["mom"], "+919876543210")

    def test_save_number_value_first(self):
        result = self.tool.run("add number 9876543210 as mom")
        self.assertIn("Saved mom", result)
        self.assertEqual(self._saved()["mom"], "+919876543210")

    def test_save_email_as(self):
        result = self.tool.run(
            "add email officialvermarohit14@gmail.com as rohit")
        self.assertIn("Saved rohit", result)
        self.assertEqual(self._saved()["rohit"],
                         "officialvermarohit14@gmail.com")

    def test_save_email_name_first(self):
        result = self.tool.run("save contact boss boss@corp.com")
        self.assertIn("Saved boss", result)
        self.assertEqual(self._saved()["boss"], "boss@corp.com")

    def test_invalid_number_rejected(self):
        result = self.tool.run("save contact mom hello123")
        self.assertIn("doesn't look like", result)
        self.assertNotIn("mom", self._saved())

    def test_list_contacts(self):
        self.tool.run("save contact mom 9876543210")
        listing = self.tool.run("show my contacts")
        self.assertIn("mom", listing)
        self.assertIn("+919876543210", listing)

    def test_overwrite_existing(self):
        self.tool.run("save contact mom 9876543210")
        self.tool.run("save contact mom 9999911111")
        self.assertEqual(self._saved()["mom"], "+919999911111")


if __name__ == "__main__":
    unittest.main()