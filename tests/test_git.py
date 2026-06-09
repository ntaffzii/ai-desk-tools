import shutil
import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import git


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class GitToolTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git"):
            self.skipTest("git is not installed")
        self.mcp = FakeMCP()
        git.register(self.mcp)

    def test_git_status_is_read_only_and_available(self):
        result = self.mcp.tools["git_status"](repo_path=str(REPO_ROOT), porcelain=True)
        self.assertIn("success", result)
        if not result["success"]:
            self.assertIn(result.get("error") or result.get("returncode"), ("git_not_found", 128))

    def test_git_diff_accepts_pathspec(self):
        result = self.mcp.tools["git_diff"](repo_path=str(REPO_ROOT), pathspec="README.md")
        self.assertIn("success", result)
        self.assertIn("command", result)
        self.assertIn("-- README.md", result["command"])

    def test_git_show_blocks_option_like_revision(self):
        result = self.mcp.tools["git_show"](repo_path=str(REPO_ROOT), revision="--help")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_revision")


if __name__ == "__main__":
    unittest.main()
