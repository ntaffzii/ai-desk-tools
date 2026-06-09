import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import package


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class PackageToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        package.register(self.mcp)

    def test_detect_package_managers_for_this_repo(self):
        result = self.mcp.tools["detect_package_managers"](str(TOOLS_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("python", result["ecosystems"])
        self.assertTrue(any(item["file"] == "requirements.txt" for item in result["manifests"]))

    def test_read_package_manifest_shape(self):
        result = self.mcp.tools["read_package_manifest"](str(TOOLS_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("manifests", result)
        self.assertIn("python", result)

    def test_list_dependencies_from_requirements(self):
        result = self.mcp.tools["list_dependencies"](str(TOOLS_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)
        self.assertTrue(any(item["scope"] == "requirements.txt" for item in result["dependencies"]))

    def test_lockfile_status_shape(self):
        result = self.mcp.tools["get_lockfile_status"](str(TOOLS_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("status", result)
        self.assertIn("warnings", result)

    def test_summarize_dependency_health_shape(self):
        result = self.mcp.tools["summarize_dependency_health"](str(TOOLS_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("dependency_counts", result)

    def test_blocks_package_outside_allowed_roots(self):
        result = self.mcp.tools["detect_package_managers"](str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
