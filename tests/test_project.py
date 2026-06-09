import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import project


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class ProjectToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        project.register(self.mcp)

    def test_detect_project_stack_for_this_repo(self):
        result = self.mcp.tools["detect_project_stack"](str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertTrue(result["has_git"])
        self.assertIn("mcp-tools", result["top_level_dirs"])

    def test_find_project_files_reports_readme(self):
        result = self.mcp.tools["find_project_files"](str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("README.md", result["readme"])

    def test_get_project_scripts_shape(self):
        result = self.mcp.tools["get_project_scripts"](str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("package_scripts", result)
        self.assertIn("suggested_commands", result)

    def test_summarize_project_health_shape(self):
        result = self.mcp.tools["summarize_project_health"](str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("summary", result)
        self.assertTrue(result["summary"]["has_readme"])

    def test_blocks_project_outside_allowed_roots(self):
        result = self.mcp.tools["detect_project_stack"](str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
