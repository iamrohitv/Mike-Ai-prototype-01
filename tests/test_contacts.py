import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.computer.contacts import (
    parse_vcf, load_json_contacts, resolve, is_raw_number,
)

VCF_SAMPLE = """BEGIN:VCARD
VERSION:3.0
FN:Rahul Sharma
N:Sharma;Rahul;;;
TEL;TYPE=CELL:+91 98765 43210
TEL;TYPE=HOME:011 2345 6789
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Maa
N:Maa;;;
TEL;TYPE=CELL:+919812345678
END:VCARD
BEGIN:VCARD
VERSION:3.0
FN:Broken Entry
NOTE:no phone here
END:VCARD
"""


class ContactsTest(unittest.TestCase):
    def test_parse_vcf(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".vcf", delete=False, encoding="utf-8"
        ) as f:
            f.write(VCF_SAMPLE)
            path = f.name
        try:
            contacts = parse_vcf(path)
        finally:
            os.unlink(path)
        self.assertEqual(contacts["rahul sharma"], "+919876543210")
        self.assertEqual(contacts["maa"], "+919812345678")
        # prefers CELL over HOME, skips entries without TEL
        self.assertEqual(len(contacts), 2)

    def test_load_json_contacts(self):
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write('{"Mom": "+91 90000 11111"}')
            path = f.name
        try:
            contacts = load_json_contacts(path)
        finally:
            os.unlink(path)
        self.assertEqual(contacts["mom"], "+919000011111")

    def test_resolve_exact_and_first_name(self):
        book = {
            "rahul sharma": "+919876543210",
            "maa": "+919812345678",
        }
        self.assertEqual(resolve("rahul sharma", book), "+919876543210")
        self.assertEqual(resolve("rahul", book), "+919876543210")
        self.assertEqual(resolve("MAA", book), "+919812345678")

    def test_resolve_raw_number_passthrough(self):
        self.assertEqual(resolve("+91 98765 43210", {}), "+919876543210")
        self.assertEqual(resolve("9876543210", None), "9876543210")

    def test_resolve_unknown_returns_none(self):
        book = {"rahul sharma": "+919876543210"}
        self.assertIsNone(resolve("suresh", book))

    def test_raw_number_detection(self):
        self.assertTrue(is_raw_number("+91 98765 43210"))
        self.assertFalse(is_raw_number("rahul"))


if __name__ == "__main__":
    unittest.main()