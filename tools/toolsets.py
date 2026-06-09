"""Toolset routing MCP tools.

Toolsets reduce context bloat by grouping tool groups by job type.
"""

from __future__ import annotations

import json
from pathlib import Path

from security import REPO_ROOT, audit


TOOLS_REGISTRY = REPO_ROOT / "data" / "tools.json"
TOOLSETS_REGISTRY = REPO_ROOT / "data" / "toolsets.json"


def _read_json(path: Path) -> list | dict:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _tools_by_id() -> dict[str, dict]:
    return {group.get("id", ""): group for group in _read_json(TOOLS_REGISTRY)}


def _toolset_summary(toolset: dict, tools_by_id: dict[str, dict]) -> dict:
    groups = toolset.get("toolGroups", [])
    missing = [group_id for group_id in groups if group_id not in tools_by_id]
    tool_count = sum(len(tools_by_id.get(group_id, {}).get("tools", [])) for group_id in groups)
    return {
        "id": toolset.get("id", ""),
        "title": toolset.get("title", ""),
        "description": toolset.get("description", ""),
        "recommendedWorkflows": toolset.get("recommendedWorkflows", []),
        "toolGroups": groups,
        "tool_count": tool_count,
        "missingToolGroups": missing,
    }


def register(mcp) -> None:
    """Register toolset routing tools."""

    @mcp.tool()
    def list_toolsets() -> dict:
        """List curated toolsets for common agent jobs."""
        tools_by_id = _tools_by_id()
        toolsets = [_toolset_summary(item, tools_by_id) for item in _read_json(TOOLSETS_REGISTRY)]
        audit("toolsets.list_toolsets", True, {"count": len(toolsets)})
        return {"success": True, "count": len(toolsets), "toolsets": toolsets}

    @mcp.tool()
    def get_toolset(toolset_id: str) -> dict:
        """Return one toolset with expanded tool group summaries."""
        tools_by_id = _tools_by_id()
        for item in _read_json(TOOLSETS_REGISTRY):
            if item.get("id") != toolset_id:
                continue
            groups = []
            for group_id in item.get("toolGroups", []):
                group = tools_by_id.get(group_id)
                if group:
                    groups.append(
                        {
                            "id": group["id"],
                            "title": group.get("title", ""),
                            "description": group.get("description", ""),
                            "tools": group.get("tools", []),
                        }
                    )
            audit("toolsets.get_toolset", True, {"toolset_id": toolset_id})
            return {"success": True, "toolset": _toolset_summary(item, tools_by_id), "groups": groups}
        audit("toolsets.get_toolset", False, {"toolset_id": toolset_id, "error": "toolset_not_found"})
        return {"success": False, "error": "toolset_not_found", "toolset_id": toolset_id}

    @mcp.tool()
    def recommend_toolsets(task_description: str = "", workflow_id: str = "") -> dict:
        """Recommend toolsets by workflow id or task keywords."""
        text = f"{task_description} {workflow_id}".lower()
        scored = []
        for item in _read_json(TOOLSETS_REGISTRY):
            score = 0
            if workflow_id and workflow_id in item.get("recommendedWorkflows", []):
                score += 5
            haystack = f"{item.get('id', '')} {item.get('title', '')} {item.get('description', '')}".lower()
            for keyword in ("backend", "api", "database", "frontend", "ui", "skill", "review", "release", "backup", "memory", "sandbox", "config", "test"):
                if keyword in text and keyword in haystack:
                    score += 2
            if score:
                scored.append((score, item))
        if not scored:
            scored = [(1, item) for item in _read_json(TOOLSETS_REGISTRY) if item.get("id") == "coding-basic"]
        tools_by_id = _tools_by_id()
        recommendations = [_toolset_summary(item, tools_by_id) | {"score": score} for score, item in sorted(scored, key=lambda pair: pair[0], reverse=True)]
        audit("toolsets.recommend_toolsets", True, {"workflow_id": workflow_id, "count": len(recommendations)})
        return {"success": True, "count": len(recommendations), "recommendations": recommendations}

    @mcp.tool()
    def validate_toolsets() -> dict:
        """Validate that every toolset points to existing tool groups."""
        tools_by_id = _tools_by_id()
        errors = []
        for item in _read_json(TOOLSETS_REGISTRY):
            if not item.get("id"):
                errors.append("toolset missing id")
            for group_id in item.get("toolGroups", []):
                if group_id not in tools_by_id:
                    errors.append(f"{item.get('id', '<unknown>')} references missing tool group {group_id}")
        audit("toolsets.validate_toolsets", not errors, {"error_count": len(errors)})
        return {"success": not errors, "error_count": len(errors), "errors": errors}
