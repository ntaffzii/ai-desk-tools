"""CI configuration inspection MCP tools."""

from __future__ import annotations

import os
import re
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
CI_FILE_NAMES = {
    ".gitlab-ci.yml",
    ".circleci/config.yml",
    "azure-pipelines.yml",
    "bitbucket-pipelines.yml",
    "Jenkinsfile",
}
COMMAND_RE = re.compile(r"^\s*(?:run:\s*)?(npm\s+(?:test|run\s+\w+)|python\s+-m\s+\w+|pytest\b.*|pnpm\s+\w+|yarn\s+\w+|cargo\s+\w+|go\s+test\b.*)", re.IGNORECASE)


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 6):
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            yield current / name


def _is_ci_file(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root)).replace("\\", "/")
    name = path.name
    if rel.startswith(".github/workflows/") and path.suffix.lower() in {".yml", ".yaml"}:
        return True
    if rel in CI_FILE_NAMES or name in CI_FILE_NAMES:
        return True
    return "ci" in name.lower() and path.suffix.lower() in {".yml", ".yaml", ".json"}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _workflow_summary(path: Path, root: Path) -> dict:
    text = _read(path)
    lines = text.splitlines()
    jobs = []
    in_jobs = False
    for line in lines:
        if re.match(r"^jobs:\s*$", line):
            in_jobs = True
            continue
        if in_jobs:
            match = re.match(r"^\s{2}([A-Za-z0-9_-]+):\s*$", line)
            if match:
                jobs.append(match.group(1))
            elif line and not line.startswith(" "):
                in_jobs = False
    return {
        "path": str(path),
        "relative_path": str(path.relative_to(root)),
        "mentions_push": "push" in text,
        "mentions_pull_request": "pull_request" in text,
        "mentions_schedule": "schedule" in text,
        "mentions_python": "python" in text.lower() or "pytest" in text.lower(),
        "mentions_node": "node" in text.lower() or "npm" in text.lower() or "pnpm" in text.lower() or "yarn" in text.lower(),
        "jobs": jobs,
    }


def register(mcp) -> None:
    """Register CI inspection tools."""

    @mcp.tool()
    def find_ci_files(project_path: str | None = None, max_depth: int = 6) -> dict:
        """Find likely CI configuration files."""
        try:
            root = _resolve_project(project_path)
            files = [{"path": str(path), "relative_path": str(path.relative_to(root))} for path in _iter_files(root, max_depth=max_depth) if _is_ci_file(path, root)]
        except PolicyError as exc:
            audit("ci.find_ci_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(files), "files": files}

    @mcp.tool()
    def inspect_github_actions_jobs(project_path: str | None = None) -> dict:
        """Inspect GitHub Actions workflow triggers and jobs."""
        ci_files = find_ci_files(project_path)
        if not ci_files.get("success"):
            return ci_files
        root = Path(ci_files["project_path"])
        workflows = []
        for item in ci_files["files"]:
            rel = item["relative_path"].replace("\\", "/")
            if rel.startswith(".github/workflows/"):
                workflows.append(_workflow_summary(Path(item["path"]), root))
        return {"success": True, "project_path": str(root), "count": len(workflows), "workflows": workflows}

    @mcp.tool()
    def list_ci_validation_commands(project_path: str | None = None) -> dict:
        """Extract likely validation commands from CI files."""
        ci_files = find_ci_files(project_path)
        if not ci_files.get("success"):
            return ci_files
        commands = []
        root = Path(ci_files["project_path"])
        for item in ci_files["files"]:
            path = Path(item["path"])
            for line_no, line in enumerate(_read(path).splitlines(), 1):
                match = COMMAND_RE.search(line)
                if match:
                    commands.append({"file": str(path), "relative_file": str(path.relative_to(root)), "line": line_no, "command": match.group(1).strip()})
        return {"success": True, "project_path": str(root), "count": len(commands), "commands": commands}

    @mcp.tool()
    def summarize_ci_surface(project_path: str | None = None) -> dict:
        """Summarize CI files, workflows, jobs, and validation commands."""
        files = find_ci_files(project_path)
        workflows = inspect_github_actions_jobs(project_path)
        commands = list_ci_validation_commands(project_path)
        warnings = []
        if files.get("count", 0) == 0:
            warnings.append("No CI files found")
        if workflows.get("count", 0) == 0:
            warnings.append("No GitHub Actions workflows found")
        return {
            "success": all(item.get("success") for item in (files, workflows, commands)),
            "project_path": files.get("project_path"),
            "ci_file_count": files.get("count", 0),
            "github_workflow_count": workflows.get("count", 0),
            "ci_command_count": commands.get("count", 0),
            "warnings": warnings,
        }
