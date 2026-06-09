import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
FIXTURE_ROOT = TOOLS_ROOT / "tests" / "_ops_fixture"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import backup, config, dependency_risk, release, task, test_inspection


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class OpsToolTests(unittest.TestCase):
    def _tools(self, module):
        mcp = FakeMCP()
        module.register(mcp)
        return mcp.tools

    def test_config_tools(self):
        tools = self._tools(config)
        self.assertTrue(tools["find_config_files"](str(FIXTURE_ROOT))["success"])
        self.assertGreater(tools["list_env_keys"](str(FIXTURE_ROOT))["count"], 0)
        self.assertGreater(tools["check_secret_hygiene"](str(FIXTURE_ROOT))["count"], 0)

    def test_test_inspection_tools(self):
        tools = self._tools(test_inspection)
        self.assertGreater(tools["find_test_files"](str(FIXTURE_ROOT))["count"], 0)
        self.assertTrue(tools["summarize_test_surface"](str(FIXTURE_ROOT))["success"])

    def test_task_tools(self):
        tools = self._tools(task)
        result = tools["scan_task_markers"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_dependency_risk_tools(self):
        tools = self._tools(dependency_risk)
        result = tools["find_unpinned_dependencies"](str(FIXTURE_ROOT))
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_release_tools(self):
        tools = self._tools(release)
        self.assertGreater(tools["find_release_files"](str(FIXTURE_ROOT))["count"], 0)
        self.assertGreater(tools["detect_versions"](str(FIXTURE_ROOT))["count"], 0)

    def test_backup_plan_and_create(self):
        tools = self._tools(backup)
        plan = tools["plan_backup_snapshot"](str(FIXTURE_ROOT), max_files=20)
        self.assertTrue(plan["success"])
        try:
            (FIXTURE_ROOT / ".backups").mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.skipTest(f"backup snapshot writes are unavailable in this sandbox: {exc}")
        created = tools["create_backup_snapshot"](str(FIXTURE_ROOT), str(FIXTURE_ROOT / ".backups"), max_files=20)
        self.assertTrue(created["success"])
        self.assertTrue(Path(created["archive_path"]).exists())

    def test_blocks_outside_allowed_roots(self):
        for module, tool_name in (
            (config, "find_config_files"),
            (test_inspection, "find_test_files"),
            (task, "scan_task_markers"),
            (dependency_risk, "find_unpinned_dependencies"),
            (release, "find_release_files"),
        ):
            tools = self._tools(module)
            result = tools[tool_name](str(REPO_ROOT.parent))
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
