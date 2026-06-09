"""Safe sandbox planning MCP tools."""

from __future__ import annotations

import py_compile
import time
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


def register(mcp) -> None:
    """Register sandbox helper tools."""

    @mcp.tool()
    def check_sandbox_available(base_dir: str = "C:/tmp") -> dict:
        """Check whether a sandbox base directory is available under allowed roots."""
        try:
            path = resolve_allowed_path(base_dir, access="write")
            path.mkdir(parents=True, exist_ok=True)
        except PolicyError as exc:
            return policy_error_result(exc)
        except OSError as exc:
            return {"success": False, "error": "sandbox_unavailable", "message": str(exc)}
        return {"success": True, "base_dir": str(path), "exists": path.exists()}

    @mcp.tool()
    def create_temp_workspace(base_dir: str = "C:/tmp", prefix: str = "ai-desk") -> dict:
        """Create a temporary workspace folder under an allowed root."""
        try:
            base = resolve_allowed_path(base_dir, access="write")
            base.mkdir(parents=True, exist_ok=True)
            path = base / f"{prefix}-{int(time.time())}"
            path.mkdir(parents=False, exist_ok=False)
        except PolicyError as exc:
            audit("sandbox.create_temp_workspace", False, {"error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            return {"success": False, "error": "workspace_create_failed", "message": str(exc)}
        return {"success": True, "workspace": str(path)}

    @mcp.tool()
    def compile_python_snippet(code: str, base_dir: str = "C:/tmp") -> dict:
        """Write and compile a Python snippet without executing it."""
        workspace = create_temp_workspace(base_dir, "py-compile")
        if not workspace.get("success"):
            return workspace
        path = Path(workspace["workspace"]) / "snippet.py"
        path.write_text(code, encoding="utf-8")
        try:
            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as exc:
            return {"success": False, "workspace": workspace["workspace"], "path": str(path), "error": "compile_failed", "message": str(exc)}
        return {"success": True, "workspace": workspace["workspace"], "path": str(path)}

    @mcp.tool()
    def plan_sandbox_run(language: str, purpose: str = "") -> dict:
        """Plan a sandboxed experiment without executing arbitrary code."""
        return {"success": True, "language": language, "purpose": purpose, "recommended_flow": ["Create temp workspace", "Copy only needed fixture files", "Compile or validate first", "Run only allowlisted commands", "Keep outputs inside sandbox workspace"]}
