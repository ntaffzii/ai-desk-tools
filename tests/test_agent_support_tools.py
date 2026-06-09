import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
FIXTURE_ROOT = TOOLS_ROOT / "tests" / "_agent_fixture"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import browser, github, memory, sandbox, structured_data


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class AgentSupportToolTests(unittest.TestCase):
    def _tools(self, module):
        mcp = FakeMCP()
        module.register(mcp)
        return mcp.tools

    def test_structured_data_read_and_path(self):
        tools = self._tools(structured_data)
        result = tools["get_json_path"](str(FIXTURE_ROOT / "config.json"), "tools.0.id")
        self.assertTrue(result["success"])
        self.assertEqual(result["value"], "demo")

    def test_structured_data_yaml_when_available(self):
        tools = self._tools(structured_data)
        result = tools["get_yaml_path"](str(FIXTURE_ROOT / "workflow.yml"), "jobs.test.runs-on")
        if result.get("error") == "yaml_unavailable":
            self.skipTest("PyYAML is not installed in this runtime")
        self.assertTrue(result["success"])
        self.assertEqual(result["value"], "ubuntu-latest")

    def test_memory_tools(self):
        tools = self._tools(memory)
        memory_path = "C:/tmp/ai-desk-test-memory.jsonl"
        try:
            saved = tools["save_memory"]("Decision: use structured data tools", "test,decision", memory_path)
        except OSError as exc:
            self.skipTest(f"memory writes unavailable in this sandbox: {exc}")
        if not saved.get("success") and saved.get("error") == "memory_write_failed":
            self.skipTest(saved.get("message", "memory write failed"))
        self.assertTrue(saved["success"])
        search = tools["search_memory"]("structured", memory_path)
        self.assertTrue(search["success"])

    def test_github_tools(self):
        tools = self._tools(github)
        context = tools["detect_github_context"](str(FIXTURE_ROOT))
        self.assertTrue(context["success"])
        workflows = tools["find_github_workflows"](str(FIXTURE_ROOT))
        self.assertEqual(workflows["count"], 1)
        draft = tools["draft_pr_description"]("Title", "Summary", "Tests")
        self.assertIn("## Summary", draft["body"])

    def test_browser_tools(self):
        tools = self._tools(browser)
        html = tools["inspect_static_html"](str(FIXTURE_ROOT / "index.html"))
        self.assertTrue(html["success"])
        self.assertEqual(html["title"], "Agent Fixture")
        self.assertEqual(html["form_count"], 1)

    def test_sandbox_tools(self):
        tools = self._tools(sandbox)
        available = tools["check_sandbox_available"]("C:/tmp")
        if not available.get("success"):
            self.skipTest(available.get("message", "sandbox unavailable"))
        compiled = tools["compile_python_snippet"]("x = 1\n", "C:/tmp")
        if not compiled.get("success") and compiled.get("error") == "workspace_create_failed":
            self.skipTest(compiled.get("message", "workspace create failed"))
        self.assertTrue(compiled["success"])

    def test_blocks_outside_allowed_roots(self):
        for module, tool_name in (
            (structured_data, "read_json"),
            (github, "detect_github_context"),
            (browser, "find_localhost_urls"),
        ):
            tools = self._tools(module)
            result = tools[tool_name](str(REPO_ROOT.parent))
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
