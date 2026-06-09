"""Release note and version inspection MCP tools."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}
VERSION_RE = re.compile(r"\b\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?\b")


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 5):
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            yield current / name


def register(mcp) -> None:
    """Register release inspection tools."""

    @mcp.tool()
    def find_release_files(project_path: str | None = None) -> dict:
        """Find changelog, release note, version, and package metadata files."""
        try:
            root = _resolve_project(project_path)
            names = ("changelog", "release", "version", "package.json", "pyproject.toml")
            files = [{"path": str(path), "relative_path": str(path.relative_to(root))} for path in _iter_files(root) if any(name in path.name.lower() for name in names)]
        except PolicyError as exc:
            audit("release.find_release_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(files), "files": files}

    @mcp.tool()
    def detect_versions(project_path: str | None = None) -> dict:
        """Detect version strings from common metadata files."""
        try:
            root = _resolve_project(project_path)
            versions = []
            package_json = root / "package.json"
            if package_json.exists():
                data = json.loads(package_json.read_text(encoding="utf-8"))
                if data.get("version"):
                    versions.append({"source": "package.json", "version": data["version"]})
            for path in _iter_files(root):
                if path.suffix.lower() not in {".md", ".txt", ".toml"}:
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")[:80_000]
                for version in sorted(set(VERSION_RE.findall(text)))[:20]:
                    versions.append({"source": str(path.relative_to(root)), "version": version})
        except PolicyError as exc:
            audit("release.detect_versions", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        except Exception:
            versions = []
        return {"success": True, "project_path": str(root), "count": len(versions), "versions": versions}

    @mcp.tool()
    def draft_release_checklist(project_path: str | None = None) -> dict:
        """Return a release readiness checklist from local release signals."""
        files = find_release_files(project_path)
        versions = detect_versions(project_path)
        checklist = [
            {"item": "Changelog or release notes exist", "ok": files.get("count", 0) > 0},
            {"item": "Version string detected", "ok": versions.get("count", 0) > 0},
            {"item": "Run validation before release", "ok": None},
            {"item": "Review git diff before release", "ok": None},
        ]
        return {"success": files.get("success") and versions.get("success"), "project_path": files.get("project_path"), "checklist": checklist}
