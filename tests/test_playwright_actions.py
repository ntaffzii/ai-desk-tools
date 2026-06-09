import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import playwright_actions


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class PlaywrightActionsTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        playwright_actions.register(self.mcp)

    def test_rejects_unsupported_url_scheme(self):
        result = self.mcp.tools["playwright_click"]("ftp://example.test", "#x")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "unsupported_url_scheme")

    def test_run_ui_check_invalid_json(self):
        result = self.mcp.tools["playwright_run_ui_check"]("http://localhost:3000", "{bad json")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_actions_json")

    def test_run_ui_check_actions_must_be_list(self):
        result = self.mcp.tools["playwright_run_ui_check"]("http://localhost:3000", "{}")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "actions_must_be_list")

    def test_accessibility_snapshot_rejects_bad_scheme(self):
        result = self.mcp.tools["playwright_accessibility_snapshot"]("ftp://example.test")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "unsupported_url_scheme")

    def test_start_session_rejects_bad_scheme(self):
        result = self.mcp.tools["playwright_start_session"]("ftp://example.test")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "unsupported_url_scheme")

    def test_use_session_missing_session(self):
        result = self.mcp.tools["playwright_use_session"]("missing-session")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "session_not_found")

    def test_use_session_invalid_json_for_existing_session(self):
        playwright_actions._SESSIONS["fake"] = {"page": object(), "console_errors": [], "network_failures": [], "created_at": 0, "last_used_at": 0}
        try:
            result = self.mcp.tools["playwright_use_session"]("fake", "{bad json")
        finally:
            playwright_actions._SESSIONS.pop("fake", None)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "invalid_actions_json")

    def test_list_sessions_empty(self):
        playwright_actions._SESSIONS.clear()
        result = self.mcp.tools["playwright_list_sessions"]()
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 0)

    def test_close_session_missing_session(self):
        result = self.mcp.tools["playwright_close_session"]("missing-session")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "session_not_found")


if __name__ == "__main__":
    unittest.main()
