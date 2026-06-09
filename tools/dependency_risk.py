"""Offline dependency risk inspection MCP tools."""

from __future__ import annotations

import re
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path
from tools import package as package_tools


RISKY_VERSION_RE = re.compile(r"^\s*(\*|latest|next|beta|alpha|rc)\s*$", re.IGNORECASE)


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    return root


def _deps(root: Path) -> list[dict]:
    node = package_tools._node_details(root)
    python = package_tools._python_details(root)
    deps = []
    for scope in ("dependencies", "dev_dependencies", "peer_dependencies"):
        for name, version in node.get(scope, {}).items():
            deps.append({"ecosystem": "node", "scope": scope, "name": name, "version": str(version)})
    for item in python.get("requirements", []) or []:
        deps.append({"ecosystem": "python", "scope": "requirements.txt", "name": item, "version": None})
    return deps


def register(mcp) -> None:
    """Register dependency risk tools."""

    @mcp.tool()
    def find_unpinned_dependencies(project_path: str | None = None) -> dict:
        """Find dependency entries that look floating or loosely pinned."""
        try:
            root = _resolve_project(project_path)
            findings = []
            for dep in _deps(root):
                version = dep.get("version") or dep["name"]
                if RISKY_VERSION_RE.search(version) or version.startswith(("^", "~", ">=", ">", "<")) or "==" not in version and dep["ecosystem"] == "python":
                    findings.append(dep)
        except PolicyError as exc:
            audit("dependency_risk.find_unpinned_dependencies", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        audit("dependency_risk.find_unpinned_dependencies", True, {"project_path": str(root), "count": len(findings)})
        return {"success": True, "project_path": str(root), "count": len(findings), "findings": findings}

    @mcp.tool()
    def find_high_risk_dependency_names(project_path: str | None = None) -> dict:
        """Flag dependency names commonly worth extra review."""
        try:
            root = _resolve_project(project_path)
            keywords = ("exec", "shell", "eval", "crypto", "jwt", "auth", "upload", "request", "http", "proxy")
            findings = [dep for dep in _deps(root) if any(word in dep["name"].lower() for word in keywords)]
        except PolicyError as exc:
            audit("dependency_risk.find_high_risk_dependency_names", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(findings), "findings": findings}

    @mcp.tool()
    def summarize_dependency_risk(project_path: str | None = None) -> dict:
        """Summarize offline dependency risk signals."""
        unpinned = find_unpinned_dependencies(project_path)
        names = find_high_risk_dependency_names(project_path)
        return {
            "success": unpinned.get("success") and names.get("success"),
            "project_path": unpinned.get("project_path"),
            "unpinned_count": unpinned.get("count", 0),
            "high_risk_name_count": names.get("count", 0),
            "warnings": ["Offline-only heuristic; does not query vulnerability databases"],
        }
