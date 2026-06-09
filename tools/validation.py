"""Validation runner MCP tools.

These tools plan and run safe validation commands through the shared command
allowlist. They avoid making agents guess which test/lint command to run.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from security import PolicyError, assert_command_allowed, audit, load_policy, policy_error_result, resolve_allowed_path


def _resolve_project(path: str | None) -> Path:
    return resolve_allowed_path(path or ".", access="execute")


def _read_package_scripts(root: Path) -> dict[str, str]:
    package_json = root / "package.json"
    if not package_json.exists():
        return {}
    try:
        data = json.loads(package_json.read_text(encoding="utf-8"))
    except Exception:
        return {}
    scripts = data.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _suggest_commands(root: Path) -> list[dict]:
    suggestions: list[dict] = []
    package_scripts = _read_package_scripts(root)
    for script_name, command in (
        ("test", "npm test"),
        ("lint", "npm run lint"),
        ("typecheck", "npm run typecheck"),
        ("build", "npm run build"),
    ):
        if script_name in package_scripts:
            suggestions.append(
                {
                    "id": f"npm:{script_name}",
                    "command": command,
                    "source": "package.json",
                    "script": script_name,
                    "script_command": package_scripts[script_name],
                }
            )

    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        suggestions.append({"id": "python:pytest", "command": "python -m pytest", "source": "python"})

    return suggestions


def _policy_status(command: str) -> dict:
    try:
        tokens = assert_command_allowed(command)
        executable = tokens[0].strip('"') if tokens else ""
        return {"allowed": True, "tokens": tokens, "executable": executable, "available": shutil.which(executable) is not None}
    except PolicyError as exc:
        return {"allowed": False, "error": exc.code, "message": exc.message, **exc.details}


def _run(command: str, cwd: Path, timeout_seconds: int, max_output_chars: int) -> dict:
    try:
        tokens = assert_command_allowed(command)
    except PolicyError as exc:
        audit("validation.run_command", False, {"command": command, "cwd": str(cwd), "error": exc.code})
        return policy_error_result(exc)

    timeout_seconds = min(max(1, timeout_seconds), 600)
    max_output_chars = min(max(1_000, max_output_chars), load_policy().max_command_output_chars)

    try:
        result = subprocess.run(
            tokens,
            cwd=str(cwd),
            shell=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        audit("validation.run_command", False, {"command": command, "cwd": str(cwd), "error": "timeout"})
        return {"success": False, "error": "timeout", "command": command, "timeout_seconds": timeout_seconds, "stdout": exc.stdout, "stderr": exc.stderr}

    audit("validation.run_command", result.returncode == 0, {"command": command, "cwd": str(cwd), "returncode": result.returncode})
    return {
        "success": result.returncode == 0,
        "command": command,
        "cwd": str(cwd),
        "returncode": result.returncode,
        "stdout": result.stdout[:max_output_chars],
        "stderr": result.stderr[:max_output_chars],
        "stdout_truncated": len(result.stdout) > max_output_chars,
        "stderr_truncated": len(result.stderr) > max_output_chars,
    }


def register(mcp) -> None:
    """Register validation tools."""

    @mcp.tool()
    def plan_validation(project_path: str | None = None) -> dict:
        """Suggest validation commands and show whether policy allows them."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("validation.plan_validation", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        suggestions = []
        for item in _suggest_commands(root):
            suggestions.append({**item, "policy": _policy_status(item["command"])})

        audit("validation.plan_validation", True, {"project_path": str(root), "suggestion_count": len(suggestions)})
        return {"success": True, "project_path": str(root), "suggestions": suggestions}

    @mcp.tool()
    def check_validation_command(command: str, project_path: str | None = None) -> dict:
        """Check whether a validation command is available and allowed before running it."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("validation.check_validation_command", False, {"project_path": project_path, "command": command, "error": exc.code})
            return policy_error_result(exc)

        status = _policy_status(command)
        audit("validation.check_validation_command", status.get("allowed", False), {"project_path": str(root), "command": command, "status": status})
        return {"success": True, "project_path": str(root), "command": command, "policy": status}

    @mcp.tool()
    def run_validation(command: str, project_path: str | None = None, timeout_seconds: int = 120, max_output_chars: int = 80_000) -> dict:
        """Run one allowlisted validation command."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("validation.run_validation", False, {"project_path": project_path, "command": command, "error": exc.code})
            return policy_error_result(exc)
        return _run(command, root, timeout_seconds, max_output_chars)

    @mcp.tool()
    def run_suggested_validations(project_path: str | None = None, max_commands: int = 2, timeout_seconds: int = 120) -> dict:
        """Run the first allowed suggested validation commands for a project."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("validation.run_suggested_validations", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        max_commands = min(max(1, max_commands), 5)
        selected = []
        for item in _suggest_commands(root):
            status = _policy_status(item["command"])
            if status.get("allowed"):
                selected.append(item)
            if len(selected) >= max_commands:
                break

        results = [_run(item["command"], root, timeout_seconds, load_policy().max_command_output_chars) for item in selected]
        audit("validation.run_suggested_validations", all(result.get("success") for result in results), {"project_path": str(root), "count": len(results)})
        return {"success": all(result.get("success") for result in results), "project_path": str(root), "commands_run": [item["command"] for item in selected], "results": results}
