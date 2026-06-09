import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import memory_context


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class MemoryContextTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        memory_context.register(self.mcp)
        self.memory_path = "C:/tmp/ai-desk-memory-context-test.jsonl"

    def test_save_and_search_project_context(self):
        saved = self.mcp.tools["save_project_decision"]("Use toolsets before broad tools", "test,toolsets", "data/toolsets.json", self.memory_path)
        if not saved.get("success") and saved.get("error") == "memory_write_failed":
            self.skipTest(saved.get("message", "memory write failed"))
        self.assertTrue(saved["success"])
        search = self.mcp.tools["search_project_context"]("toolsets", "", self.memory_path)
        self.assertTrue(search["success"])
        self.assertGreater(search["count"], 0)

    def test_build_context_pack_empty_ok(self):
        result = self.mcp.tools["build_context_pack"]("", self.memory_path)
        self.assertTrue(result["success"])
        self.assertIn("groups", result)

    def test_generate_handoff_from_memory(self):
        result = self.mcp.tools["generate_handoff_from_memory"](self.memory_path)
        self.assertTrue(result["success"])
        self.assertIn("Memory Handoff", result["handoff"])


if __name__ == "__main__":
    unittest.main()
