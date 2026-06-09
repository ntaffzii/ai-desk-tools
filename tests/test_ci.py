import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = TOOLS_ROOT / "tests" / "_agent_fixture"
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import ci


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class CiToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        ci.register(self.mcp)

    def test_find_ci_files(self):
        result = self.mcp.tools["find_ci_files"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_inspect_github_actions_jobs(self):
        result = self.mcp.tools["inspect_github_actions_jobs"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    def test_summarize_ci_surface(self):
        result = self.mcp.tools["summarize_ci_surface"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["ci_file_count"], 0)

    def test_blocks_outside_allowed_roots(self):
        result = self.mcp.tools["find_ci_files"](str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
