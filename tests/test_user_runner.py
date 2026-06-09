import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import user_runner


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class UserRunnerToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        user_runner.register(self.mcp)

    def test_list_templates(self):
        result = self.mcp.tools["list_user_run_templates"]()
        self.assertTrue(result["success"])
        self.assertTrue(any(item["id"] == "github_split" for item in result["templates"]))

    def test_plan_user_run_command_warns_network(self):
        result = self.mcp.tools["plan_user_run_command"]("git push -u origin main", "publish", "high")
        self.assertTrue(result["success"])
        self.assertTrue(result["warnings"])

    def test_write_user_run_template(self):
        result = self.mcp.tools["write_user_run_template"]("validate_all", str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertTrue(Path(result["path"]).exists())
        self.assertIn("run-validate-all.ps1", result["path"])

    def test_write_unknown_template(self):
        result = self.mcp.tools["write_user_run_template"]("missing-template", str(REPO_ROOT))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "unknown_template")

    def test_validate_user_run_script(self):
        written = self.mcp.tools["write_user_run_template"]("git_publish_skill_agents", str(REPO_ROOT))
        self.assertTrue(written["success"])
        result = self.mcp.tools["validate_user_run_script"](written["path"])
        self.assertTrue(result["success"])
        self.assertIn("git push", result["risk_hints"])

    def test_blocks_outside_allowed_roots(self):
        result = self.mcp.tools["write_user_run_template"]("validate_all", str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
