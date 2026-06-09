import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import validation


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class ValidationToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        validation.register(self.mcp)

    def test_plan_validation_shape(self):
        result = self.mcp.tools["plan_validation"](str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("suggestions", result)

    def test_check_validation_command_allowed(self):
        result = self.mcp.tools["check_validation_command"]("git status --short", str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertTrue(result["policy"]["allowed"])

    def test_check_validation_command_denied(self):
        result = self.mcp.tools["check_validation_command"]("git reset --hard", str(REPO_ROOT))
        self.assertTrue(result["success"])
        self.assertFalse(result["policy"]["allowed"])
        self.assertEqual(result["policy"]["error"], "command_not_allowlisted")

    def test_run_validation_blocks_non_allowlisted_command(self):
        result = self.mcp.tools["run_validation"]("git reset --hard", str(REPO_ROOT))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "command_not_allowlisted")

    def test_run_suggested_validations_runs_selected_with_mock(self):
        suggestions = [{"id": "git-status", "command": "git status --short", "source": "test"}]
        with patch.object(validation, "_suggest_commands", return_value=suggestions), patch.object(validation, "_run", return_value={"success": True, "command": "git status --short"}):
            result = self.mcp.tools["run_suggested_validations"](str(REPO_ROOT), max_commands=1)
        self.assertTrue(result["success"])
        self.assertEqual(result["commands_run"], ["git status --short"])


if __name__ == "__main__":
    unittest.main()
