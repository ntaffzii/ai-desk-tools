import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = TOOLS_ROOT / "tests" / "_repo_index_fixture"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import repo_index


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class RepoIndexToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        repo_index.register(self.mcp)

    def test_build_repo_index(self):
        result = self.mcp.tools["build_repo_index"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["file_count"], 4)
        self.assertIn("source", result["counts_by_kind"])

    def test_search_repo_index_finds_symbol(self):
        result = self.mcp.tools["search_repo_index"]("normalize_widget_name", str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)
        self.assertEqual(result["matches"][0]["relative_path"], "src\\widget.py")

    def test_find_related_files(self):
        result = self.mcp.tools["find_related_files"](str(FIXTURE_ROOT / "src" / "widget.py"), str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        related_paths = [item["relative_path"] for item in result["related_files"]]
        self.assertIn("src\\widget.test.py", related_paths)

    def test_summarize_index(self):
        result = self.mcp.tools["summarize_index"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["source_file_count"], 0)
        self.assertTrue(any(item["relative_path"] == "README.md" for item in result["entry_points"]))

    def test_blocks_outside_allowed_roots(self):
        result = self.mcp.tools["build_repo_index"](str(FIXTURE_ROOT.parents[3]))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
