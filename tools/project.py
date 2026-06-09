"""Project inspection MCP tools.

These tools are read-only and summarize project structure so agents can choose
the right workflow, tests, and tools before editing.
"""

from __future__ import annotations

import json
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


PACKAGE_MANIFESTS = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "Pipfile": "python",
    "poetry.lock": "python",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "composer.json": "php",
    "Gemfile": "ruby",
}

CONFIG_HINTS = {
    "tsconfig.json": "typescript",
    "vite.config.ts": "vite",
    "vite.config.js": "vite",
    "next.config.js": "nextjs",
    "next.config.mjs": "nextjs",
    "tailwind.config.js": "tailwind",
    "eslint.config.js": "eslint",
    ".eslintrc": "eslint",
    ".prettierrc": "prettier",
    "pytest.ini": "pytest",
    "tox.ini": "tox",
    "ruff.toml": "ruff",
    ".ruff.toml": "ruff",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker-compose",
}


def _resolve_project(path: str | None) -> Path:
    return resolve_allowed_path(path or ".", access="read")


def _safe_read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _top_level_files(root: Path) -> list[str]:
    try:
        return sorted(item.name for item in root.iterdir() if item.is_file())
    except OSError:
        return []


def _top_level_dirs(root: Path) -> list[str]:
    ignored = {".git", "__pycache__", "node_modules", ".venv", "venv"}
    try:
        return sorted(item.name for item in root.iterdir() if item.is_dir() and item.name not in ignored)
    except OSError:
        return []


def _detect_manifests(root: Path) -> list[dict]:
    files = set(_top_level_files(root))
    return [
        {"file": name, "ecosystem": ecosystem, "path": str(root / name)}
        for name, ecosystem in PACKAGE_MANIFESTS.items()
        if name in files
    ]


def _detect_configs(root: Path) -> list[dict]:
    files = set(_top_level_files(root))
    return [
        {"file": name, "type": config_type, "path": str(root / name)}
        for name, config_type in CONFIG_HINTS.items()
        if name in files
    ]


def _read_package_scripts(root: Path) -> dict:
    package_json = root / "package.json"
    if not package_json.exists():
        return {}
    data = _safe_read_json(package_json)
    scripts = data.get("scripts", {})
    return scripts if isinstance(scripts, dict) else {}


def _python_test_hints(root: Path) -> list[str]:
    hints = []
    if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
        hints.append("python -m pytest")
    if (root / "tox.ini").exists():
        hints.append("tox")
    return hints


def _node_test_hints(root: Path) -> list[str]:
    scripts = _read_package_scripts(root)
    hints = []
    for name in ("test", "lint", "typecheck", "build"):
        if name in scripts:
            hints.append(f"npm run {name}" if name != "test" else "npm test")
    return hints


def _has_git(root: Path) -> bool:
    return (root / ".git").exists()


def register(mcp) -> None:
    """Register project inspection tools."""

    @mcp.tool()
    def detect_project_stack(project_path: str | None = None) -> dict:
        """Detect likely project ecosystems and frameworks from top-level files."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("project.detect_project_stack", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        manifests = _detect_manifests(root)
        configs = _detect_configs(root)
        ecosystems = sorted({item["ecosystem"] for item in manifests})
        frameworks = sorted({item["type"] for item in configs})
        result = {
            "success": True,
            "project_path": str(root),
            "ecosystems": ecosystems,
            "frameworks_or_tools": frameworks,
            "manifests": manifests,
            "configs": configs,
            "has_git": _has_git(root),
            "top_level_dirs": _top_level_dirs(root),
        }
        audit("project.detect_project_stack", True, {"project_path": str(root), "ecosystems": ecosystems})
        return result

    @mcp.tool()
    def get_project_scripts(project_path: str | None = None) -> dict:
        """Return package scripts and inferred test/lint/build hints."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("project.get_project_scripts", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        package_scripts = _read_package_scripts(root)
        hints = _node_test_hints(root) + _python_test_hints(root)
        result = {
            "success": True,
            "project_path": str(root),
            "package_scripts": package_scripts,
            "suggested_commands": hints,
        }
        audit("project.get_project_scripts", True, {"project_path": str(root), "suggested_count": len(hints)})
        return result

    @mcp.tool()
    def find_project_files(project_path: str | None = None) -> dict:
        """Return important top-level files and folders."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("project.find_project_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        files = _top_level_files(root)
        result = {
            "success": True,
            "project_path": str(root),
            "readme": [name for name in files if name.lower().startswith("readme")],
            "license": [name for name in files if name.lower().startswith("license")],
            "manifests": [item["file"] for item in _detect_manifests(root)],
            "configs": [item["file"] for item in _detect_configs(root)],
            "top_level_dirs": _top_level_dirs(root),
        }
        audit("project.find_project_files", True, {"project_path": str(root)})
        return result

    @mcp.tool()
    def summarize_project_health(project_path: str | None = None) -> dict:
        """Return a lightweight project health summary without running commands."""
        try:
            root = _resolve_project(project_path)
        except PolicyError as exc:
            audit("project.summarize_project_health", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)

        stack = _detect_manifests(root)
        configs = _detect_configs(root)
        files = _top_level_files(root)
        scripts = _read_package_scripts(root)
        suggested_commands = _node_test_hints(root) + _python_test_hints(root)
        warnings = []

        if not any(name.lower().startswith("readme") for name in files):
            warnings.append("README not found at project root")
        if not stack:
            warnings.append("No recognized package manifest found")
        if stack and not suggested_commands:
            warnings.append("No obvious test/lint/build command detected")
        if not _has_git(root):
            warnings.append("Git repository not detected at project root")

        result = {
            "success": True,
            "project_path": str(root),
            "summary": {
                "ecosystems": sorted({item["ecosystem"] for item in stack}),
                "frameworks_or_tools": sorted({item["type"] for item in configs}),
                "has_readme": any(name.lower().startswith("readme") for name in files),
                "has_license": any(name.lower().startswith("license") for name in files),
                "has_git": _has_git(root),
                "script_count": len(scripts),
                "suggested_commands": suggested_commands,
                "warnings": warnings,
            },
        }
        audit("project.summarize_project_health", True, {"project_path": str(root), "warning_count": len(warnings)})
        return result
