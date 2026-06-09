import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import playwright_tools


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class PlaywrightToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        playwright_tools.register(self.mcp)

    def test_check_runtime_shape(self):
        result = self.mcp.tools["check_playwright_runtime"]()
        self.assertIn("success", result)
        self.assertIn("available", result)

    def test_smoke_plan(self):
        result = self.mcp.tools["playwright_smoke_plan"]("http://localhost:3000")
        self.assertTrue(result["success"])
        self.assertGreater(len(result["steps"]), 0)

    def test_rejects_unsupported_url_scheme(self):
        result = self.mcp.tools["playwright_inspect_page"]("ftp://example.test")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "unsupported_url_scheme")


if __name__ == "__main__":
    unittest.main()
