import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
FIXTURE_ROOT = TOOLS_ROOT / "tests" / "_ops_fixture"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import security_scanner


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class SecurityScannerTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        security_scanner.register(self.mcp)

    def test_scan_secrets_in_repo(self):
        result = self.mcp.tools["scan_secrets_in_repo"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_scan_env_exposure(self):
        result = self.mcp.tools["scan_env_exposure"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_generate_security_report(self):
        result = self.mcp.tools["generate_security_report"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertIn("summary", result)

    def test_blocks_outside_allowed_roots(self):
        result = self.mcp.tools["scan_secrets_in_repo"](str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
