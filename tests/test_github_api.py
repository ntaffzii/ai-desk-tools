import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import github_api


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class GitHubApiTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        github_api.register(self.mcp)

    def test_check_auth_shape(self):
        result = self.mcp.tools["check_github_api_auth"]()
        self.assertTrue(result["success"])
        self.assertIn("token_present", result)

    def test_missing_token_does_not_call_network(self):
        with patch.dict("os.environ", {}, clear=True):
            result = self.mcp.tools["get_repo_info"]("owner", "repo")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "github_token_missing")

    def test_draft_pr_review(self):
        result = self.mcp.tools["draft_pr_review"]("Looks good", "No blockers", "Tests pass")
        self.assertTrue(result["success"])
        self.assertIn("## Summary", result["body"])


if __name__ == "__main__":
    unittest.main()
