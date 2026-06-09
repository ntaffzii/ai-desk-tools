"""Read-only Git MCP tools."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from security import PolicyError, assert_command_allowed, audit, load_policy, policy_error_result, resolve_allowed_path


def _repo_path(repo_path: str | None) -> Path | None:
    if not repo_path:
        return None
    return resolve_allowed_path(repo_path, access="read")


def _run_git(args: list[str], repo_path: str | None = None, timeout_seconds: int = 30, max_output_chars: int | None = None) -> dict:
    command = "git " + " ".join(args)
    action = f"git.{args[0] if args else 'unknown'}"

    try:
        tokens = assert_command_allowed(command)
        cwd = _repo_path(repo_path)
    except PolicyError as exc:
        audit(action, False, {"command": command, "repo_path": repo_path, "error": exc.code})
        return policy_error_result(exc)

    if not shutil.which("git"):
        audit(action, False, {"command": command, "repo_path": repo_path, "error": "git_not_found"})
        return {"success": False, "error": "git_not_found"}

    max_output_chars = max_output_chars or load_policy().max_command_output_chars
    max_output_chars = min(max(1_000, max_output_chars), load_policy().max_command_output_chars)
    timeout_seconds = min(max(1, timeout_seconds), 120)

    try:
        result = subprocess.run(
            tokens,
            cwd=str(cwd) if cwd else None,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        audit(action, False, {"command": command, "repo_path": repo_path, "error": "timeout"})
        return {"success": False, "error": "timeout", "command": command, "stdout": exc.stdout, "stderr": exc.stderr}

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    audit(action, result.returncode == 0, {"command": command, "repo_path": str(cwd) if cwd else None, "returncode": result.returncode})
    return {
        "success": result.returncode == 0,
        "command": command,
        "repo_path": str(cwd) if cwd else None,
        "returncode": result.returncode,
        "stdout": stdout[:max_output_chars],
        "stderr": stderr[:max_output_chars],
        "stdout_truncated": len(stdout) > max_output_chars,
        "stderr_truncated": len(stderr) > max_output_chars,
    }


def register(mcp) -> None:
    """Register read-only Git tools."""

    @mcp.tool()
    def git_status(repo_path: str | None = None, porcelain: bool = False) -> dict:
        """Return Git working tree status."""
        args = ["status", "--short"] if porcelain else ["status"]
        return _run_git(args, repo_path=repo_path)

    @mcp.tool()
    def git_diff(repo_path: str | None = None, staged: bool = False, pathspec: str = "", max_output_chars: int = 80_000) -> dict:
        """Return Git diff for unstaged or staged changes."""
        args = ["diff", "--cached"] if staged else ["diff"]
        if pathspec:
            if pathspec.startswith("-"):
                return {"success": False, "error": "invalid_pathspec", "message": "pathspec must not start with '-'"}
            args.extend(["--", pathspec])
        return _run_git(args, repo_path=repo_path, max_output_chars=max_output_chars)

    @mcp.tool()
    def git_log(repo_path: str | None = None, limit: int = 10, oneline: bool = True) -> dict:
        """Return recent Git commits."""
        limit = min(max(1, limit), 100)
        args = ["log", f"-n{limit}"]
        if oneline:
            args.append("--oneline")
        return _run_git(args, repo_path=repo_path)

    @mcp.tool()
    def git_show(repo_path: str | None = None, revision: str = "HEAD", max_output_chars: int = 80_000) -> dict:
        """Show a commit or object. Read-only."""
        if revision.startswith("-"):
            return {"success": False, "error": "invalid_revision", "message": "revision must not start with '-'"}
        return _run_git(["show", "--stat", "--patch", revision], repo_path=repo_path, max_output_chars=max_output_chars)

    @mcp.tool()
    def git_branch(repo_path: str | None = None, all_branches: bool = False) -> dict:
        """List Git branches."""
        args = ["branch", "--all"] if all_branches else ["branch", "--show-current"]
        return _run_git(args, repo_path=repo_path)
