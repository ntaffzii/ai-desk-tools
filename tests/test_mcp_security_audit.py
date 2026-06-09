import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import mcp_security_audit


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class McpSecurityAuditTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        mcp_security_audit.register(self.mcp)

    def test_audit_tool_risk_levels(self):
        result = self.mcp.tools["audit_tool_risk_levels"]()
        self.assertTrue(result["success"])
        self.assertGreater(len(result["groups"]), 0)

    def test_find_mutating_tools(self):
        result = self.mcp.tools["find_mutating_tools"]()
        self.assertTrue(result["success"])
        self.assertIn("tools", result)

    def test_check_tool_policy_coverage(self):
        result = self.mcp.tools["check_tool_policy_coverage"]()
        self.assertTrue(result["success"])
        self.assertIn("allowed_command_prefix_count", result)

    def test_summarize_attack_surface(self):
        result = self.mcp.tools["summarize_mcp_attack_surface"]()
        self.assertTrue(result["success"])
        self.assertIn("counts_by_risk", result)


if __name__ == "__main__":
    unittest.main()
