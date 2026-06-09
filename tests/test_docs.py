import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import docs


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class DocsToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        docs.register(self.mcp)

    def test_find_documentation_reports_readme(self):
        result = self.mcp.tools["find_documentation"](str(REPO_ROOT), max_depth=3)
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)
        self.assertTrue(any(item["relative_path"] == "README.md" for item in result["documents"]))

    def test_read_documentation_file_reads_readme(self):
        result = self.mcp.tools["read_documentation_file"](str(REPO_ROOT / "README.md"), max_chars=200)
        self.assertTrue(result["success"])
        self.assertIn("Skill Agents", result["content"])

    def test_summarize_documentation_index_shape(self):
        result = self.mcp.tools["summarize_documentation_index"](str(REPO_ROOT), max_depth=3)
        self.assertTrue(result["success"])
        self.assertIn("counts_by_kind", result)
        self.assertIn("entry_points", result)

    def test_build_context_bundle_includes_readme(self):
        result = self.mcp.tools["build_context_bundle"](str(REPO_ROOT), max_files=2, max_chars_per_file=300)
        self.assertTrue(result["success"])
        self.assertGreater(result["selected_count"], 0)
        self.assertTrue(any(item["relative_path"] == "README.md" for item in result["files"]))

    def test_find_docs_by_keyword(self):
        result = self.mcp.tools["find_docs_by_keyword"]("Skill Agents", str(REPO_ROOT), max_depth=3)
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_blocks_docs_outside_allowed_roots(self):
        result = self.mcp.tools["find_documentation"](str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
