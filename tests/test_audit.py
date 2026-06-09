import sys
import unittest
from pathlib import Path
from unittest.mock import patch


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import audit as audit_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class AuditToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        audit_tools.register(self.mcp)
        self.events = [
            {"ts": "2026-06-08T10:00:00+0700", "action": "filesystem.read_file", "success": True, "details": {"path": "README.md"}},
            {
                "ts": "2026-06-08T10:01:00+0700",
                "action": "system.run_command",
                "success": False,
                "details": {"error": "command_not_allowlisted", "command": "git reset --hard"},
            },
        ]

    def test_read_audit_log_filters_success(self):
        with patch.object(audit_tools, "_read_events", return_value=self.events), patch.object(audit_tools, "audit"):
            result = self.mcp.tools["read_audit_log"](success=False)
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["events"][0]["action"], "system.run_command")

    def test_summarize_audit_log_counts_errors(self):
        with patch.object(audit_tools, "_read_events", return_value=self.events), patch.object(audit_tools, "audit"):
            result = self.mcp.tools["summarize_audit_log"]()
        self.assertTrue(result["success"])
        self.assertEqual(result["event_count"], 2)
        self.assertEqual(result["by_error"]["command_not_allowlisted"], 1)

    def test_find_policy_denials(self):
        with patch.object(audit_tools, "_read_events", return_value=self.events), patch.object(audit_tools, "audit"):
            result = self.mcp.tools["find_policy_denials"]()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    def test_find_audit_events(self):
        with patch.object(audit_tools, "_read_events", return_value=self.events), patch.object(audit_tools, "audit"):
            result = self.mcp.tools["find_audit_events"](action_contains="filesystem")
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)


if __name__ == "__main__":
    unittest.main()
