import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.reasoning.brain import Brain
from memory.store import MemoryStore
from policies.engine import PolicyEngine
from tools.registry import build_tools


class ToolRouterTest(unittest.TestCase):
    def _setup(self):
        tmp = tempfile.TemporaryDirectory()
        store = MemoryStore(os.path.join(tmp.name, "m.db"))
        tools = build_tools(store, PolicyEngine())
        brain = Brain(store, config={"local_url": "", "global_url": "", "global_key": ""})
        return tmp, store, tools, brain

    def test_fallback_routes_git(self):
        tmp, store, tools, brain = self._setup()
        tool = brain._fallback_route("stage my changes in git", tools)
        store.close()
        tmp.cleanup()
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "git")

    def test_fallback_routes_file(self):
        tmp, store, tools, brain = self._setup()
        tool = brain._fallback_route("open the config file for me", tools)
        store.close()
        tmp.cleanup()
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "file")

    def test_fallback_returns_none_for_chat(self):
        tmp, store, tools, brain = self._setup()
        tool = brain._fallback_route("how is your day going", tools)
        store.close()
        tmp.cleanup()
        self.assertIsNone(tool)

    def test_fallback_routes_system(self):
        tmp, store, tools, brain = self._setup()
        tool = brain._fallback_route("tell me the disk free space", tools)
        store.close()
        tmp.cleanup()
        self.assertIsNotNone(tool)
        self.assertEqual(tool.name, "system")


if __name__ == "__main__":
    unittest.main()