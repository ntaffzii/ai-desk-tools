"""Runtime registry and policy introspection tools."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

from security import REPO_ROOT, TOOLS_ROOT, audit, load_policy


TOOLS_REGISTRY = REPO_ROOT / "data" / "tools.json"
WORKFLOWS_REGISTRY = REPO_ROOT / "data" / "workflows.json"
TOOLSETS_REGISTRY = REPO_ROOT / "data" / "toolsets.json"


def _read_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _module_exists(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def _tool_group_summary(group: dict) -> dict:
    module_path = REPO_ROOT / group.get("module", "")
    return {
        "id": group.get("id", ""),
        "title": group.get("title", ""),
        "description": group.get("description", ""),
        "module": group.get("module", ""),
        "module_exists": module_path.exists(),
        "tool_count": len(group.get("tools", [])),
        "tools": group.get("tools", []),
        "recommendedSkills": group.get("recommendedSkills", []),
        "recommendedWorkflows": group.get("recommendedWorkflows", []),
    }


def register(mcp) -> None:
    """Register registry and policy introspection tools."""

    @mcp.tool()
    def list_available_tools(group_id: str = "") -> dict:
        """List registered tool groups and tools from data/tools.json."""
        groups = _read_json(TOOLS_REGISTRY)
        if group_id:
            groups = [group for group in groups if group.get("id") == group_id]
        result = [_tool_group_summary(group) for group in groups]
        audit("registry.list_available_tools", True, {"group_id": group_id, "count": len(result)})
        return {"success": True, "count": len(result), "groups": result}

    @mcp.tool()
    def get_tool_group(group_id: str) -> dict:
        """Return one tool group by id."""
        groups = _read_json(TOOLS_REGISTRY)
        for group in groups:
            if group.get("id") == group_id:
                audit("registry.get_tool_group", True, {"group_id": group_id})
                return {"success": True, "group": _tool_group_summary(group)}
        audit("registry.get_tool_group", False, {"group_id": group_id, "error": "tool_group_not_found"})
        return {"success": False, "error": "tool_group_not_found", "group_id": group_id}

    @mcp.tool()
    def list_allowed_roots() -> dict:
        """Return directories that filesystem and command tools may access."""
        policy = load_policy()
        roots = [{"path": str(root), "exists": root.exists()} for root in policy.allowed_roots]
        audit("registry.list_allowed_roots", True, {"count": len(roots)})
        return {"success": True, "allowed_roots": roots}

    @mcp.tool()
    def get_tool_policy() -> dict:
        """Return current high-risk tool policy in structured form."""
        policy = load_policy()
        result = {
            "allowed_roots": [str(root) for root in policy.allowed_roots],
            "audit_log": str(policy.audit_log),
            "max_file_read_chars": policy.max_file_read_chars,
            "max_command_output_chars": policy.max_command_output_chars,
            "commands": {
                "allow_shell_control_operators": policy.allow_shell_control_operators,
                "allowed_prefixes": [" ".join(prefix) for prefix in policy.allowed_command_prefixes],
                "blocked_executables": list(policy.blocked_executables),
            },
        }
        audit("registry.get_tool_policy", True, {})
        return {"success": True, "policy": result}

    @mcp.tool()
    def explain_tool_policy() -> dict:
        """Explain the current security policy in agent-friendly terms."""
        policy = load_policy()
        explanations = [
            "File tools may only access configured allowed_roots.",
            "Write tools create backups when configured by the caller.",
            "Command tools are allowlisted by command prefix.",
            "Shell control operators are blocked unless the policy explicitly allows them.",
            "Destructive executables are blocked.",
            "High-risk actions are written to the audit log.",
        ]
        audit("registry.explain_tool_policy", True, {})
        return {
            "success": True,
            "summary": "AI Desk Tools uses a shared policy layer for filesystem, command, and audit behavior.",
            "allowed_roots": [str(root) for root in policy.allowed_roots],
            "audit_log": str(policy.audit_log),
            "rules": explanations,
            "next_step_when_blocked": "Use a read-only tool first, choose a narrower path/command, or update config/tool_policy.json intentionally.",
        }

    @mcp.tool()
    def list_available_workflows(workflow_id: str = "") -> dict:
        """List workflow playbooks from data/workflows.json."""
        workflows = _read_json(WORKFLOWS_REGISTRY)
        if workflow_id:
            workflows = [workflow for workflow in workflows if workflow.get("id") == workflow_id]
        result = [
            {
                "id": workflow.get("id", ""),
                "title": workflow.get("title", ""),
                "description": workflow.get("description", ""),
                "path": workflow.get("path", ""),
                "path_exists": (REPO_ROOT / workflow.get("path", "")).exists(),
                "recommendedSkills": workflow.get("recommendedSkills", []),
                "step_count": len(workflow.get("steps", [])),
            }
            for workflow in workflows
        ]
        audit("registry.list_available_workflows", True, {"workflow_id": workflow_id, "count": len(result)})
        return {"success": True, "count": len(result), "workflows": result}

    @mcp.tool()
    def get_runtime_capabilities() -> dict:
        """Return installed optional dependencies and external command availability."""
        capabilities = {
            "python_modules": {
                "mcp": _module_exists("mcp"),
                "fastmcp": _module_exists("fastmcp"),
                "requests": _module_exists("requests"),
                "bs4": _module_exists("bs4"),
                "ddgs": _module_exists("ddgs"),
                "playwright": _module_exists("playwright"),
                "PIL": _module_exists("PIL"),
                "cv2": _module_exists("cv2"),
                "pyautogui": _module_exists("pyautogui"),
            },
            "commands": {
                "git": shutil.which("git"),
                "python": shutil.which("python"),
                "pytest": shutil.which("pytest"),
                "npm": shutil.which("npm"),
                "yt-dlp": shutil.which("yt-dlp"),
                "mpv": shutil.which("mpv"),
            },
            "paths": {
                "repo_root": str(REPO_ROOT),
                "tools_root": str(TOOLS_ROOT),
                "tools_registry": str(TOOLS_REGISTRY),
                "workflows_registry": str(WORKFLOWS_REGISTRY),
                "toolsets_registry": str(TOOLSETS_REGISTRY),
            },
        }
        audit("registry.get_runtime_capabilities", True, {})
        return {"success": True, "capabilities": capabilities}
