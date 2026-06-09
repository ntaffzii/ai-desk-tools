"""Task marker inspection MCP tools."""

from __future__ import annotations

import os
import re
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|NOTE|BUG|XXX)\b[:\-\s]*(.*)", re.IGNORECASE)


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 8, max_file_size: int = 500_000):
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            path = current / name
            try:
                if path.stat().st_size <= max_file_size:
                    yield path
            except OSError:
                continue


def register(mcp) -> None:
    """Register task marker tools."""

    @mcp.tool()
    def scan_task_markers(project_path: str | None = None, max_depth: int = 8, limit: int = 200) -> dict:
        """Scan files for TODO/FIXME/HACK/BUG markers."""
        try:
            root = _resolve_project(project_path)
            matches = []
            for path in _iter_files(root, max_depth=max_depth):
                try:
                    for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                        match = MARKER_RE.search(line)
                        if match:
                            matches.append({"file": str(path), "relative_file": str(path.relative_to(root)), "line": line_no, "marker": match.group(1).upper(), "text": match.group(2).strip()})
                        if len(matches) >= limit:
                            break
                except OSError:
                    continue
                if len(matches) >= limit:
                    break
        except PolicyError as exc:
            audit("task.scan_task_markers", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        audit("task.scan_task_markers", True, {"project_path": str(root), "count": len(matches)})
        return {"success": True, "project_path": str(root), "count": len(matches), "markers": matches}

    @mcp.tool()
    def find_roadmap_files(project_path: str | None = None) -> dict:
        """Find likely roadmap, issue, task, and changelog planning files."""
        try:
            root = _resolve_project(project_path)
            names = ("roadmap", "todo", "tasks", "issues", "backlog", "changelog")
            files = []
            for path in _iter_files(root, max_depth=5):
                if any(name in path.name.lower() for name in names):
                    files.append({"path": str(path), "relative_path": str(path.relative_to(root))})
        except PolicyError as exc:
            audit("task.find_roadmap_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(files), "files": files}

    @mcp.tool()
    def summarize_task_markers(project_path: str | None = None) -> dict:
        """Summarize local task markers by marker type."""
        result = scan_task_markers(project_path)
        counts = {}
        for item in result.get("markers", []):
            counts[item["marker"]] = counts.get(item["marker"], 0) + 1
        return {"success": result.get("success"), "project_path": result.get("project_path"), "counts_by_marker": counts, "total": result.get("count", 0)}
