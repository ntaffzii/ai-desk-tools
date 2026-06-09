import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import registry


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class RegistryToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        registry.register(self.mcp)

    def test_list_available_tools_includes_registry_group(self):
        result = self.mcp.tools["list_available_tools"]()
        self.assertTrue(result["success"])
        ids = {group["id"] for group in result["groups"]}
        self.assertIn("registry", ids)
        self.assertIn("filesystem", ids)
        self.assertIn("project", ids)
        self.assertIn("audit", ids)
        self.assertIn("validation", ids)

    def test_get_tool_group_returns_one_group(self):
        result = self.mcp.tools["get_tool_group"]("registry")
        self.assertTrue(result["success"])
        self.assertEqual(result["group"]["id"], "registry")
        self.assertIn("get_tool_policy", result["group"]["tools"])

    def test_get_missing_tool_group_fails_cleanly(self):
        result = self.mcp.tools["get_tool_group"]("missing")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "tool_group_not_found")

    def test_policy_tools_return_allowed_roots(self):
        roots = self.mcp.tools["list_allowed_roots"]()
        policy = self.mcp.tools["get_tool_policy"]()
        explanation = self.mcp.tools["explain_tool_policy"]()
        self.assertTrue(roots["success"])
        self.assertTrue(policy["success"])
        self.assertTrue(explanation["success"])
        self.assertGreaterEqual(len(roots["allowed_roots"]), 1)

    def test_list_available_workflows(self):
        result = self.mcp.tools["list_available_workflows"]()
        self.assertTrue(result["success"])
        ids = {workflow["id"] for workflow in result["workflows"]}
        self.assertIn("ship-feature", ids)

    def test_runtime_capabilities_shape(self):
        result = self.mcp.tools["get_runtime_capabilities"]()
        self.assertTrue(result["success"])
        self.assertIn("python_modules", result["capabilities"])
        self.assertIn("commands", result["capabilities"])


if __name__ == "__main__":
    unittest.main()
