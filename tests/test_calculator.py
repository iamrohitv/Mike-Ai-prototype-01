import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.computer.calculator_tool import CalculatorTool


class CalculatorToolTest(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        store = MemoryStore(os.path.join(tmp.name, "m.db"))
        tool = CalculatorTool(store, PolicyEngine())
        return tmp, store, tool

    def test_matches_arithmetic_request(self):
        tmp, store, tool = self._setup()
        self.assertTrue(tool.matches("calculate 12 * 8 + 4"))
        self.assertTrue(tool.matches("what is 2+2?"))
        self.assertTrue(tool.matches("5 * (3 + 2)"))
        store.close()
        tmp.cleanup()

    def test_rejects_non_math(self):
        tmp, store, tool = self._setup()
        self.assertFalse(tool.matches("how is your day going"))
        self.assertFalse(tool.matches("what is your name"))
        store.close()
        tmp.cleanup()

    def test_basic_operations(self):
        tmp, store, tool = self._setup()
        cases = {
            "calculate 2 + 3": "5",
            "12 * 8": "96",
            "10 / 4": "2.5",
            "2 ^ 10": "1024",
            "(4 + 6) * 2": "20",
        }
        for request in ["calculate 2 + 3", "12 * 8", "10 / 4", "2 ^ 10", "(4 + 6) * 2"]:
            result = tool.run(request)
            expected = cases[request]
            self.assertIn(expected, result)
        store.close()
        tmp.cleanup()

    def test_division_by_zero(self):
        tmp, store, tool = self._setup()
        result = tool.run("5 / 0")
        self.assertIn("undefined", result)
        store.close()
        tmp.cleanup()

    def test_rejects_dangerous_input(self):
        tmp, store, tool = self._setup()
        self.assertFalse(tool.matches("__import__('os').system('dir')"))
        store.close()
        tmp.cleanup()

    def test_verify(self):
        tmp, store, tool = self._setup()
        result = tool.run("1 + 1")
        self.assertNotEqual(tool.verify(result), "failed")
        store.close()
        tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
