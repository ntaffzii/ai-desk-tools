import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
FIXTURE_ROOT = REPO_ROOT / "mcp-tools" / "tests" / "_api_fixture"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import api


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class ApiToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        api.register(self.mcp)

    def test_find_api_files(self):
        result = self.mcp.tools["find_api_files"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 2)

    def test_extract_api_endpoints(self):
        result = self.mcp.tools["extract_api_endpoints"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        paths = {item["path"] for item in result["endpoints"]}
        self.assertIn("/users", paths)
        self.assertIn("/login", paths)

    def test_find_openapi_specs(self):
        result = self.mcp.tools["find_openapi_specs"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["specs"][0]["summary"]["endpoint_count"], 2)

    def test_find_api_config(self):
        result = self.mcp.tools["find_api_config"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertTrue(any("https://api.example.test/v1" in item["urls"] for item in result["hints"]))

    def test_summarize_api_surface(self):
        result = self.mcp.tools["summarize_api_surface"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["endpoint_count"], 2)

    def test_blocks_api_outside_allowed_roots(self):
        result = self.mcp.tools["find_api_files"](str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
