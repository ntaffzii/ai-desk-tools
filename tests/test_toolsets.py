import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import toolsets


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class ToolsetTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        toolsets.register(self.mcp)

    def test_list_toolsets(self):
        result = self.mcp.tools["list_toolsets"]()
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_get_toolset_expands_groups(self):
        result = self.mcp.tools["get_toolset"]("backend-review")
        self.assertTrue(result["success"])
        self.assertGreater(len(result["groups"]), 0)

    def test_recommend_toolsets(self):
        result = self.mcp.tools["recommend_toolsets"]("review backend api database", "review-pr")
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_validate_toolsets(self):
        result = self.mcp.tools["validate_toolsets"]()
        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()
