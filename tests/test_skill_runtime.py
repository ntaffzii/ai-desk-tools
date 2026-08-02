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

    def test_primary_workflow_has_stronger_toolset_priority(self):
        toolsets = skill_runtime._recommend_toolsets(
            "Build a responsive SaaS dashboard with accessible forms",
            ["frontend-interface", "build-mcp-tool"],
            5,
        )
        ids = [item["id"] for item in toolsets]
        self.assertIn("frontend-ui", ids[:2])
        self.assertIn("design-frontend", ids[:2])


class TfidfScoringTests(unittest.TestCase):
    """Direct unit coverage for the TF-IDF cosine-similarity scorer, not just
    end-to-end routing behavior -- these pin down the math itself."""

    def test_cosine_similarity_of_identical_vectors_is_one(self):
        vec = {"apple": 0.5, "banana": 0.2}
        self.assertAlmostEqual(skill_runtime._cosine_similarity(vec, vec), 1.0)

    def test_cosine_similarity_with_no_shared_terms_is_zero(self):
        vec_a = {"apple": 1.0}
        vec_b = {"banana": 1.0}
        self.assertEqual(skill_runtime._cosine_similarity(vec_a, vec_b), 0.0)

    def test_cosine_similarity_handles_empty_vectors(self):
        self.assertEqual(skill_runtime._cosine_similarity({}, {"apple": 1.0}), 0.0)
        self.assertEqual(skill_runtime._cosine_similarity({}, {}), 0.0)

    def test_idf_weighs_rare_terms_higher_than_common_terms(self):
        # "common" appears in all 3 documents; "rare" appears in only 1.
        docs = [
            ["common", "rare", "widget"],
            ["common", "gadget"],
            ["common", "sprocket"],
        ]
        idf = skill_runtime._build_idf(docs)
        self.assertGreater(idf["rare"], idf["common"])

    def test_score_does_not_simply_grow_with_haystack_length(self):
        # A short, highly focused haystack should not lose to a long haystack
        # that only shares generic/common words with the query -- this is
        # the specific failure mode the old raw-token-overlap scorer had.
        query = "thai invoice vat withholding tax"
        haystacks = [
            "thai invoice vat withholding tax revenue code",  # short, highly relevant
            "generic task management report summary review workflow document "
            "planning organize schedule track update status notes",  # long, no overlap
        ]
        scores = skill_runtime._cosine_score_batch(query, haystacks)
        self.assertGreater(scores[0], scores[1])
        self.assertEqual(scores[1], 0.0)

    def test_distinctive_shared_term_scores_higher_than_only_common_terms(self):
        query = "promptpay qr checksum validation"
        haystacks = [
            "thai id validate promptpay qr checksum",  # shares the distinctive terms
            "use this skill for any task involving",  # shares only filler words (all below the 2-char min or common)
        ]
        scores = skill_runtime._cosine_score_batch(query, haystacks)
        self.assertGreater(scores[0], scores[1])


if __name__ == "__main__":
    unittest.main()
