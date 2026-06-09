import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from tools import code_editing


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


class CodeEditingTests(unittest.TestCase):
    def setUp(self):
        self.mcp = FakeMCP()
        code_editing.register(self.mcp)
        self.scratch = REPO_ROOT / "mcp-tools" / "tests" / "scratch"
        try:
            self.scratch.mkdir(parents=True, exist_ok=True)
        except (FileNotFoundError, PermissionError) as exc:
            self.skipTest(f"filesystem writes are unavailable in this environment: {exc}")

    def test_write_and_edit_file_inside_allowed_root(self):
        target = self.scratch / "sample.txt"
        result = self.mcp.tools["write_file"](str(target), "hello\nworld\n", overwrite=True, create_backup=False)
        self.assertTrue(result["success"])

        edit = self.mcp.tools["edit_file_specific"](str(target), "world", "agent", create_backup=True)
        self.assertTrue(edit["success"])
        self.assertEqual(target.read_text(encoding="utf-8"), "hello\nagent\n")
        self.assertTrue(edit["backup_path"])

    def test_refuses_ambiguous_replace(self):
        target = self.scratch / "ambiguous.txt"
        target.write_text("x\nx\n", encoding="utf-8")
        result = self.mcp.tools["edit_file_specific"](str(target), "x", "y", replace_all=False)
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "target_not_unique")

    def test_blocks_write_outside_allowed_root(self):
        outside = REPO_ROOT.parent / "outside-skill-agents-test.txt"
        result = self.mcp.tools["write_file"](str(outside), "nope")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "path_outside_allowed_roots")


if __name__ == "__main__":
    unittest.main()
