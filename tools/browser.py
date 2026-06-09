"""Browser readiness and local UI inspection MCP tools."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


LOCALHOST_RE = re.compile(r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0):\d+[^\s'\"`)]*")


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    return root


def register(mcp) -> None:
    """Register browser helper tools."""

    @mcp.tool()
    def check_browser_capabilities() -> dict:
        """Check local browser automation readiness."""
        return {"success": True, "commands": {"node": shutil.which("node"), "npx": shutil.which("npx")}, "python_playwright_available": shutil.which("playwright") is not None}

    @mcp.tool()
    def find_localhost_urls(project_path: str | None = None, max_files: int = 200) -> dict:
        """Find localhost URLs mentioned in project files."""
        try:
            root = _resolve_project(project_path)
            urls = set()
            for current_root, dirs, files in os.walk(root):
                dirs[:] = [name for name in dirs if name not in {".git", "node_modules", ".venv", "venv", "__pycache__"}]
                for name in files[:max_files]:
                    path = Path(current_root) / name
                    try:
                        urls.update(LOCALHOST_RE.findall(path.read_text(encoding="utf-8", errors="replace")[:100_000]))
                    except OSError:
                        continue
        except PolicyError as exc:
            audit("browser.find_localhost_urls", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(urls), "urls": sorted(urls)}

    @mcp.tool()
    def inspect_static_html(file_path: str) -> dict:
        """Inspect a local HTML file for title, scripts, styles, and forms without opening a browser."""
        try:
            path = resolve_allowed_path(file_path, access="read")
            text = path.read_text(encoding="utf-8", errors="replace")
        except PolicyError as exc:
            return policy_error_result(exc)
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        return {"success": True, "path": str(path), "title": title.group(1).strip() if title else "", "script_count": len(re.findall(r"<script\b", text, re.IGNORECASE)), "style_count": len(re.findall(r"<style\b|<link\b[^>]+stylesheet", text, re.IGNORECASE)), "form_count": len(re.findall(r"<form\b", text, re.IGNORECASE))}

    @mcp.tool()
    def plan_browser_check(url: str) -> dict:
        """Return a browser smoke-check plan for a URL."""
        steps = ["Open the URL", "Check page title and visible errors", "Inspect console errors", "Inspect failed network requests", "Capture screenshot if UI changed"]
        return {"success": True, "url": url, "steps": steps}
