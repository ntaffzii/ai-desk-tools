import json
import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
MEMORY_FILE = REPO_ROOT / "mcp-tools" / "tests" / "_memory_fixture.jsonl"
sys.path.insert(0, str(TOOLS_ROOT))

from tools import browser_page_map, external_mcp_catalog, figma, notion, postgres, slack_discord, vector_memory


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def tools_for(module):
    mcp = FakeMCP()
    module.register(mcp)
    return mcp.tools


class NewIntegrationTests(unittest.TestCase):
    def test_external_mcp_catalog_plans(self):
        tools = tools_for(external_mcp_catalog)
        result = tools["search_mcp_catalogs"]("notion")
        self.assertTrue(result["success"])
        self.assertGreater(result["count"], 0)

    def test_browser_page_map(self):
        tools = tools_for(browser_page_map)
        html = "<title>Demo</title><main><h1>Hello</h1><button>Save</button><input placeholder='Name'><a href='/x'>X</a></main>"
        result = tools["capture_page_map_from_html"](html, "https://example.com")
        self.assertTrue(result["success"])
        self.assertEqual(result["title"], "Demo")
        self.assertEqual(result["counts"]["interactive_elements"], 2)
        found = tools["find_element_by_label"](html, "save")
        self.assertEqual(found["count"], 1)

    def test_vector_memory_search(self):
        tools = tools_for(vector_memory)
        result = tools["search_vector_memory"]("obsidian notion", str(MEMORY_FILE))
        self.assertTrue(result["success"])
        self.assertEqual(result["count"], 1)

    def test_postgres_risk(self):
        tools = tools_for(postgres)
        self.assertTrue(tools["explain_sql_risk"]("select * from users")["readonly"])
        self.assertFalse(tools["explain_sql_risk"]("drop table users")["readonly"])

    def test_figma_no_auth_and_plans(self):
        tools = tools_for(figma)
        auth = tools["check_figma_auth"]()
        self.assertTrue(auth["success"])
        plan = tools["plan_figma_inspection"]("https://www.figma.com/file/ABC123/Demo")
        self.assertEqual(plan["file_key"], "ABC123")

    def test_notion_plans_without_auth(self):
        tools = tools_for(notion)
        plan = tools["create_notion_note_plan"]("page-id", "Title", "Body")
        self.assertTrue(plan["success"])
        auth = tools["check_notion_auth"]()
        self.assertTrue(auth["success"])

    def test_slack_discord_offline_helpers(self):
        tools = tools_for(slack_discord)
        messages = json.dumps([{"user": "a", "text": "please fix this"}, {"user": "b", "text": "ok"}])
        summary = tools["summarize_channel_messages"](messages)
        self.assertTrue(summary["success"])
        actions = tools["extract_action_items"](messages)
        self.assertEqual(actions["count"], 1)


if __name__ == "__main__":
    unittest.main()
