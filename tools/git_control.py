"""Controlled Git mutation MCP tools."""

from __future__ import annotations

import shlex
import shutil
import subprocess
from pathlib import Path

from security import PolicyError, assert_command_allowed, audit, load_policy, policy_error_result, resolve_allowed_path


def _repo_path(repo_path: str | None) -> Path | None:
    return resolve_allowed_path(repo_path, access="write") if repo_path else None


def _safe_ref(value: str, label: str) -> str:
    value = value.strip()
    if not value or value.startswith("-") or any(ch.isspace() for ch in value):
        raise PolicyError(f"invalid_{label}", f"{label} must be non-empty, not start with '-', and contain no whitespace", {label: value})
    return value


def _pathspecs(raw: str) -> list[str]:
    items = [item.strip() for item in raw.split(",") if item.strip()]
    for item in items:
        if item.startswith("-"):
            raise PolicyError("invalid_pathspec", "pathspec must not start with '-'", {"pathspec": item})
    return items


def _run(command: list[str], repo_path: str | None, action: str, timeout_seconds: int = 60) -> dict:
    if not shutil.which("git"):
        return {"success": False, "error": "git_not_found"}

    command_text = " ".join(shlex.quote(part) for part in command)
    try:
        tokens = assert_command_allowed(command_text)
        cwd = _repo_path(repo_path)
    except PolicyError as exc:
        audit(action, False, {"command": command_text, "repo_path": repo_path, "error": exc.code})
        return policy_error_result(exc)

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
        audit(action, False, {"command": command_text, "repo_path": repo_path, "error": "timeout"})
        return {"success": False, "error": "timeout", "command": command_text, "stdout": exc.stdout, "stderr": exc.stderr}

    max_chars = load_policy().max_command_output_chars
    audit(action, result.returncode == 0, {"command": command_text, "repo_path": str(cwd) if cwd else None, "returncode": result.returncode})
    return {
        "success": result.returncode == 0,
        "command": command_text,
        "repo_path": str(cwd) if cwd else None,
        "returncode": result.returncode,
        "stdout": (result.stdout or "")[:max_chars],
        "stderr": (result.stderr or "")[:max_chars],
    }


def register(mcp) -> None:
    """Register controlled Git mutation tools."""

    @mcp.tool()
    def git_create_branch(branch_name: str, repo_path: str | None = None) -> dict:
        """Create and switch to a new branch."""
        try:
            branch = _safe_ref(branch_name, "branch_name")
        except PolicyError as exc:
            return policy_error_result(exc)
        return _run(["git", "checkout", "-b", branch], repo_path, "git_control.create_branch")

    @mcp.tool()
    def git_checkout_branch(branch_name: str, repo_path: str | None = None) -> dict:
        """Switch to an existing branch."""
        try:
            branch = _safe_ref(branch_name, "branch_name")
        except PolicyError as exc:
            return policy_error_result(exc)
        return _run(["git", "checkout", branch], repo_path, "git_control.checkout_branch")

    @mcp.tool()
    def git_stage_files(pathspecs: str, repo_path: str | None = None) -> dict:
        """Stage comma-separated pathspecs."""
        try:
            paths = _pathspecs(pathspecs)
        except PolicyError as exc:
            return policy_error_result(exc)
        if not paths:
            return {"success": False, "error": "empty_pathspecs"}
        return _run(["git", "add", "--", *paths], repo_path, "git_control.stage_files")

    @mcp.tool()
    def git_unstage_files(pathspecs: str, repo_path: str | None = None) -> dict:
        """Unstage comma-separated pathspecs without changing working tree files."""
        try:
            paths = _pathspecs(pathspecs)
        except PolicyError as exc:
            return policy_error_result(exc)
        if not paths:
            return {"success": False, "error": "empty_pathspecs"}
        return _run(["git", "restore", "--staged", "--", *paths], repo_path, "git_control.unstage_files")

    @mcp.tool()
    def git_commit(message: str, repo_path: str | None = None) -> dict:
        """Create a Git commit from currently staged changes."""
        cleaned = message.strip()
        if not cleaned:
            return {"success": False, "error": "empty_commit_message"}
        return _run(["git", "commit", "-m", cleaned], repo_path, "git_control.commit", timeout_seconds=120)
