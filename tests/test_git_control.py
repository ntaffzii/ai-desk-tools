import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import git_control


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class GitControlTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        git_control.register(self.mcp)

    def test_rejects_empty_commit_message(self):
        result = self.mcp.tools["git_commit"]("", str(REPO_ROOT))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "empty_commit_message")

    def test_rejects_invalid_branch_name(self):
        result = self.mcp.tools["git_create_branch"]("--bad", str(REPO_ROOT))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_branch_name")

    def test_stage_uses_safe_command_with_mock(self):
        with patch.object(git_control, "_run", return_value={"success": True, "command": "git add -- README.md"}) as mocked:
            result = self.mcp.tools["git_stage_files"]("README.md", str(REPO_ROOT))
        self.assertTrue(result["success"])
        mocked.assert_called_once()

    def test_blocks_outside_allowed_roots(self):
        result = self.mcp.tools["git_checkout_branch"]("main", str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
