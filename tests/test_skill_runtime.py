import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS_ROOT))

from tools import skill_runtime


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def runtime_tools():
    mcp = FakeMCP()
    skill_runtime.register(mcp)
    return mcp.tools


class SkillRuntimeTests(unittest.TestCase):
    def test_build_skill_index(self):
        tools = runtime_tools()
        result = tools["build_skill_index"]()
        self.assertTrue(result["success"])
        names = {item["name"] for item in result["skills"]}
        self.assertIn("personal-agent-workflow", names)
        self.assertIn("tool-agnostic-mcp-routing", names)

    def test_route_daily_personal_agent(self):
        tools = runtime_tools()
        result = tools["route_request"]("Build today's plan from Notion Obsidian calendar email and memory")
        self.assertTrue(result["success"])
        workflow_ids = {item["id"] for item in result["workflows"]}
        skill_names = {item["name"] for item in result["skills"]}
        toolset_ids = {item["id"] for item in result["toolsets"]}
        self.assertIn("daily-personal-agent", workflow_ids)
        self.assertIn("personal-agent-workflow", skill_names)
        self.assertIn("personal-daily-agent", toolset_ids)

    def test_load_skill_and_workflow(self):
        tools = runtime_tools()
        skill = tools["load_skill"]("obsidian-notion-bridge")
        self.assertTrue(skill["success"])
        self.assertIn("Obsidian Notion Bridge", skill["content"])
        workflow = tools["load_workflow"]("personal-knowledge-sync")
        self.assertTrue(workflow["success"])
        self.assertIn("Personal Knowledge Sync", workflow["content"])

    def test_build_agent_context(self):
        tools = runtime_tools()
        result = tools["build_agent_context"]("Sync Obsidian notes to Notion as draft payloads")
        self.assertTrue(result["success"])
        self.assertIn("Workflow:", result["context"])
        self.assertIn("Skill:", result["context"])

    def test_short_prompt_needs_improver(self):
        tools = runtime_tools()
        result = tools["route_request"]("จัดให้")
        self.assertTrue(result["success"])
        self.assertTrue(result["needs_prompt_improver"])


if __name__ == "__main__":
    unittest.main()

