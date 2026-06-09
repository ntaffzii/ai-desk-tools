"""Test structure inspection MCP tools."""

from __future__ import annotations

import json
import os
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
TEST_MARKERS = ("test", "tests", "spec", "__tests__")


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 8):
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            yield current / name


def _is_test_file(path: Path, root: Path) -> bool:
    rel_parts = {part.lower() for part in path.relative_to(root).parts}
    name = path.name.lower()
    return any(marker in rel_parts for marker in TEST_MARKERS) or name.startswith("test_") or name.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts", "_test.py"))


def register(mcp) -> None:
    """Register test inspection tools."""

    @mcp.tool()
    def find_test_files(project_path: str | None = None, max_depth: int = 8, limit: int = 200) -> dict:
        """Find likely test files."""
        try:
            root = _resolve_project(project_path)
            files = []
            for path in _iter_files(root, max_depth=max_depth):
                if _is_test_file(path, root):
                    files.append({"path": str(path), "relative_path": str(path.relative_to(root)), "size_bytes": path.stat().st_size})
                if len(files) >= max(1, min(int(limit), 500)):
                    break
        except PolicyError as exc:
            audit("test_inspection.find_test_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        audit("test_inspection.find_test_files", True, {"project_path": str(root), "count": len(files)})
        return {"success": True, "project_path": str(root), "count": len(files), "files": files}

    @mcp.tool()
    def detect_test_frameworks(project_path: str | None = None) -> dict:
        """Detect likely test frameworks from manifests and config files."""
        try:
            root = _resolve_project(project_path)
            frameworks = set()
            package_json = root / "package.json"
            if package_json.exists():
                data = json.loads(package_json.read_text(encoding="utf-8"))
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                for name in ("jest", "vitest", "mocha", "playwright", "cypress"):
                    if name in deps:
                        frameworks.add(name)
            for filename, framework in (("pytest.ini", "pytest"), ("tox.ini", "tox"), ("vitest.config.ts", "vitest"), ("playwright.config.ts", "playwright")):
                if (root / filename).exists():
                    frameworks.add(framework)
            if any(path.name.startswith("test_") and path.suffix == ".py" for path in _iter_files(root, 4)):
                frameworks.add("unittest-or-pytest")
        except PolicyError as exc:
            audit("test_inspection.detect_test_frameworks", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        except Exception:
            frameworks = set()
        result = {"success": True, "project_path": str(root), "frameworks": sorted(frameworks)}
        audit("test_inspection.detect_test_frameworks", True, {"project_path": str(root), "frameworks": sorted(frameworks)})
        return result

    @mcp.tool()
    def map_source_to_tests(project_path: str | None = None, source_path: str | None = None) -> dict:
        """Find test files whose names likely correspond to a source file."""
        try:
            root = _resolve_project(project_path)
            source = Path(source_path).stem.lower() if source_path else ""
            tests = find_test_files(str(root)).get("files", [])
            matches = [item for item in tests if source and source in Path(item["relative_path"]).stem.lower()]
        except PolicyError as exc:
            audit("test_inspection.map_source_to_tests", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "source_path": source_path, "matches": matches}

    @mcp.tool()
    def summarize_test_surface(project_path: str | None = None) -> dict:
        """Summarize test files and likely frameworks."""
        files = find_test_files(project_path)
        frameworks = detect_test_frameworks(project_path)
        return {
            "success": files.get("success") and frameworks.get("success"),
            "project_path": files.get("project_path"),
            "test_file_count": files.get("count", 0),
            "frameworks": frameworks.get("frameworks", []),
            "warnings": [] if files.get("count", 0) else ["No likely test files found"],
        }
