import sys
import unittest
from pathlib import Path


TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLS_ROOT.parent
sys.path.insert(0, str(TOOLS_ROOT))

from security import PolicyError, assert_command_allowed, resolve_allowed_path


class SecurityPolicyTests(unittest.TestCase):
    def test_allows_repo_root_paths(self):
        resolved = resolve_allowed_path(REPO_ROOT / "README.md")
        self.assertEqual(resolved, (REPO_ROOT / "README.md").resolve())

    def test_blocks_parent_paths(self):
        with self.assertRaises(PolicyError) as context:
            resolve_allowed_path(REPO_ROOT.parent)
        self.assertEqual(context.exception.code, "path_outside_allowed_roots")

    def test_allows_configured_command_prefix(self):
        tokens = assert_command_allowed("git status --short")
        self.assertEqual(tokens[:2], ["git", "status"])

    def test_blocks_shell_control_operators(self):
        with self.assertRaises(PolicyError) as context:
            assert_command_allowed("git status && echo unsafe")
        self.assertEqual(context.exception.code, "shell_control_operator_blocked")

    def test_blocks_non_allowlisted_command(self):
        with self.assertRaises(PolicyError) as context:
            assert_command_allowed("python arbitrary_script.py")
        self.assertEqual(context.exception.code, "command_not_allowlisted")

    def test_blocks_destructive_executable(self):
        with self.assertRaises(PolicyError) as context:
            assert_command_allowed("rm README.md")
        self.assertEqual(context.exception.code, "blocked_executable")

    def test_blocks_git_mutation_not_in_allowlist(self):
        with self.assertRaises(PolicyError) as context:
            assert_command_allowed("git reset --hard")
        self.assertEqual(context.exception.code, "command_not_allowlisted")


if __name__ == "__main__":
    unittest.main()
