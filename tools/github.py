"""GitHub repository metadata MCP tools."""

from __future__ import annotations

import json
import os
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    return root


def register(mcp) -> None:
    """Register GitHub metadata tools."""

    @mcp.tool()
    def detect_github_context(project_path: str | None = None) -> dict:
        """Detect local GitHub configuration and token availability without revealing token values."""
        try:
            root = _resolve_project(project_path)
            github_dir = root / ".github"
            token_keys = [key for key in ("GITHUB_TOKEN", "GH_TOKEN", "GITHUB_PERSONAL_ACCESS_TOKEN") if os.getenv(key)]
        except PolicyError as exc:
            audit("github.detect_github_context", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "has_github_dir": github_dir.exists(), "token_env_keys_present": token_keys}

    @mcp.tool()
    def find_github_workflows(project_path: str | None = None) -> dict:
        """Find GitHub Actions workflow files."""
        try:
            root = _resolve_project(project_path)
            workflow_dir = root / ".github" / "workflows"
            files = []
            if workflow_dir.exists():
                files = [{"path": str(path), "relative_path": str(path.relative_to(root))} for path in sorted(workflow_dir.glob("*")) if path.suffix.lower() in {".yml", ".yaml"}]
        except PolicyError as exc:
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(files), "workflows": files}

    @mcp.tool()
    def inspect_github_actions(project_path: str | None = None) -> dict:
        """Return lightweight GitHub Actions workflow metadata."""
        workflows = find_github_workflows(project_path)
        if not workflows.get("success"):
            return workflows
        summaries = []
        root = Path(workflows["project_path"])
        for item in workflows["workflows"]:
            text = Path(item["path"]).read_text(encoding="utf-8", errors="replace")
            summaries.append({"relative_path": item["relative_path"], "mentions_pull_request": "pull_request" in text, "mentions_push": "push" in text, "mentions_python": "python" in text.lower(), "mentions_node": "node" in text.lower() or "npm" in text.lower()})
        return {"success": True, "project_path": str(root), "count": len(summaries), "workflows": summaries}

    @mcp.tool()
    def draft_pr_description(title: str, summary: str, tests: str = "", risks: str = "") -> dict:
        """Draft a plain PR description from supplied local context."""
        body = f"## Summary\n\n{summary.strip()}\n\n## Tests\n\n{tests.strip() or 'Not run.'}\n\n## Risks\n\n{risks.strip() or 'None noted.'}\n"
        return {"success": True, "title": title, "body": body}
