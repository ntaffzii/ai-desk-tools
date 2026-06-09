import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
FIXTURE_ROOT = TOOLS_ROOT / "tests" / "_database_fixture"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import database


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class DatabaseToolTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        database.register(self.mcp)

    def test_find_database_files(self):
        result = self.mcp.tools["find_database_files"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["count"], 3)

    def test_extract_schema_objects(self):
        result = self.mcp.tools["extract_schema_objects"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        names = {item["name"] for item in result["objects"]}
        self.assertIn("User", names)
        self.assertIn("posts", names)
        self.assertIn("accounts", names)

    def test_find_migrations(self):
        result = self.mcp.tools["find_migrations"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    def test_find_database_config(self):
        result = self.mcp.tools["find_database_config"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertTrue(any("DATABASE_URL" in item["env_keys"] for item in result["hints"]))

    def test_summarize_database_surface(self):
        result = self.mcp.tools["summarize_database_surface"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreaterEqual(result["schema_object_count"], 3)

    def test_blocks_database_outside_allowed_roots(self):
        result = self.mcp.tools["find_database_files"](str(REPO_ROOT.parent))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
