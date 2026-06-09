import json
import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import calendar, email_inbox, issue_tracker, obsidian_notion_bridge, rag_adapter


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


class PersonalToolsTests(unittest.TestCase):
    def test_obsidian_notion_bridge_plans(self):
        tools = tools_for(obsidian_notion_bridge)
        note = REPO_ROOT / "mcp-tools" / "tests" / "_personal_note.md"
        result = tools["inspect_obsidian_note_for_notion"](str(note))
        self.assertTrue(result["success"])
        self.assertEqual(result["title"], "Personal OS")
        self.assertIn("notion", result["tags"])
        plan = tools["plan_obsidian_to_notion"](str(note), "page-id")
        self.assertTrue(plan["success"])
        self.assertEqual(plan["notion_payload"]["parent"]["page_id"], "page-id")

    def test_issue_tracker_helpers(self):
        tools = tools_for(issue_tracker)
        parsed = tools["parse_issue_reference"]("Fix ABC-123 and #42")
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["count"], 2)
        draft = tools["draft_issue_from_context"]("Inbox triage", "Need a daily plan", "github", "personal,agent")
        self.assertEqual(draft["payload"]["labels"], ["personal", "agent"])
        tasks = tools["break_down_issue"]("Build UI", "figma frontend")
        self.assertIn("Inspect Figma/page map before frontend changes.", tasks["tasks"])

    def test_calendar_helpers(self):
        tools = tools_for(calendar)
        events = json.dumps([{"title": "Planning", "start": "2026-06-09T09:00", "description": "prepare action list"}])
        summary = tools["summarize_calendar_events"](events)
        self.assertTrue(summary["success"])
        plan = tools["build_daily_plan"](events, "write docs,review inbox", "2026-06-09")
        self.assertEqual(plan["day"], "2026-06-09")
        followups = tools["extract_calendar_followups"](events)
        self.assertEqual(followups["count"], 1)

    def test_email_helpers(self):
        tools = tools_for(email_inbox)
        messages = json.dumps([{"from": "a@example.com", "subject": "Please review", "body": "Can you follow up by Friday?"}])
        summary = tools["summarize_email_messages"](messages)
        self.assertTrue(summary["success"])
        actions = tools["extract_email_action_items"](messages)
        self.assertEqual(actions["count"], 1)
        draft = tools["draft_email_reply"]("Please review", "I will review it today.")
        self.assertTrue(draft["body"].startswith("Hi,"))

    def test_rag_adapter_helpers(self):
        tools = tools_for(rag_adapter)
        providers = tools["list_rag_providers"]()
        self.assertTrue(providers["success"])
        chunks = tools["chunk_text_for_rag"]("hello world " * 200, "note-1", 300, 30)
        self.assertGreater(chunks["count"], 1)
        plan = tools["plan_rag_index"](json.dumps(["notes/a.md"]), "local-lightweight")
        self.assertTrue(plan["success"])


if __name__ == "__main__":
    unittest.main()

