"""MCP security audit tools.

These tools inspect the local MCP tool registry and policy to summarize risk,
coverage, and missing guardrails.
"""

from __future__ import annotations

import json
from pathlib import Path

from security import REPO_ROOT, audit, load_policy


TOOLS_REGISTRY = REPO_ROOT / "data" / "tools.json"

READ_WORDS = ("list", "read", "find", "get", "inspect", "summarize", "detect", "check", "validate", "search", "plan", "draft")
WRITE_WORDS = ("write", "edit", "patch", "save", "create", "stage", "unstage", "commit", "checkout", "backup", "screenshot")
EXECUTE_WORDS = ("run", "execute", "format", "test", "play", "press", "open")
DESTRUCTIVE_WORDS = ("delete", "remove", "reset", "force", "drop", "truncate", "destroy")


def _read_tools() -> list[dict]:
    if not TOOLS_REGISTRY.exists():
        return []
    return json.loads(TOOLS_REGISTRY.read_text(encoding="utf-8"))


def _risk_for_tool(tool_name: str) -> str:
    lowered = tool_name.lower()
    if any(word in lowered for word in DESTRUCTIVE_WORDS):
        return "destructive"
    if any(word in lowered for word in EXECUTE_WORDS):
        return "execute"
    if any(word in lowered for word in WRITE_WORDS):
        return "write"
    if any(word in lowered for word in READ_WORDS):
        return "read"
    return "unknown"


def _risk_rank(risk: str) -> int:
    return {"read": 1, "unknown": 2, "write": 3, "execute": 4, "destructive": 5}.get(risk, 2)


def register(mcp) -> None:
    """Register MCP security audit tools."""

    @mcp.tool()
    def audit_tool_risk_levels() -> dict:
        """Classify registered tools by heuristic risk level."""
        groups = []
        counts: dict[str, int] = {}
        for group in _read_tools():
            tools = [{"name": name, "risk": _risk_for_tool(name)} for name in group.get("tools", [])]
            for item in tools:
                counts[item["risk"]] = counts.get(item["risk"], 0) + 1
            group_risk = max((item["risk"] for item in tools), key=_risk_rank, default="unknown")
            groups.append({"id": group.get("id"), "title": group.get("title"), "group_risk": group_risk, "tools": tools})
        audit("mcp_security_audit.audit_tool_risk_levels", True, {"group_count": len(groups)})
        return {"success": True, "counts_by_risk": counts, "groups": groups}

    @mcp.tool()
    def find_mutating_tools() -> dict:
        """Return tools classified as write, execute, or destructive."""
        risk = audit_tool_risk_levels()
        mutating = []
        for group in risk.get("groups", []):
            for tool in group.get("tools", []):
                if tool["risk"] in {"write", "execute", "destructive"}:
                    mutating.append({"group_id": group["id"], "tool": tool["name"], "risk": tool["risk"]})
        audit("mcp_security_audit.find_mutating_tools", True, {"count": len(mutating)})
        return {"success": True, "count": len(mutating), "tools": mutating}

    @mcp.tool()
    def check_tool_policy_coverage() -> dict:
        """Check whether policy has expected roots, audit log, command allowlist, and blocked executables."""
        policy = load_policy()
        findings = []
        if not policy.allowed_roots:
            findings.append({"severity": "high", "message": "No allowed_roots configured"})
        if not policy.audit_log:
            findings.append({"severity": "medium", "message": "No audit_log configured"})
        if not policy.allowed_command_prefixes:
            findings.append({"severity": "high", "message": "No allowed command prefixes configured"})
        if policy.allow_shell_control_operators:
            findings.append({"severity": "high", "message": "Shell control operators are enabled"})
        blocked = set(policy.blocked_executables)
        for expected in ("rm", "del", "rmdir", "format", "shutdown", "reboot", "curl", "wget"):
            if expected not in blocked:
                findings.append({"severity": "medium", "message": f"Blocked executable missing: {expected}"})
        audit("mcp_security_audit.check_tool_policy_coverage", True, {"finding_count": len(findings)})
        return {
            "success": True,
            "finding_count": len(findings),
            "findings": findings,
            "allowed_roots": [str(root) for root in policy.allowed_roots],
            "allowed_command_prefix_count": len(policy.allowed_command_prefixes),
            "blocked_executables": list(policy.blocked_executables),
        }

    @mcp.tool()
    def summarize_mcp_attack_surface() -> dict:
        """Summarize local MCP attack surface from registry and policy."""
        risk = audit_tool_risk_levels()
        mutating = find_mutating_tools()
        policy = check_tool_policy_coverage()
        warnings = []
        counts = risk.get("counts_by_risk", {})
        if counts.get("destructive", 0):
            warnings.append("Destructive-looking tools are registered")
        if counts.get("execute", 0):
            warnings.append("Execute-capable tools are registered; keep command allowlist tight")
        if policy.get("finding_count", 0):
            warnings.append("Policy coverage findings exist")
        return {
            "success": True,
            "tool_group_count": len(risk.get("groups", [])),
            "counts_by_risk": counts,
            "mutating_tool_count": mutating.get("count", 0),
            "policy_finding_count": policy.get("finding_count", 0),
            "warnings": warnings,
        }
