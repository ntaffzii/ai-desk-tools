"""Code editing MCP tools."""

from __future__ import annotations

import difflib
import subprocess
import time
from pathlib import Path

from security import PolicyError, assert_command_allowed, audit, load_policy, policy_error_result, resolve_allowed_path


def _resolve(path: str) -> Path:
    return resolve_allowed_path(path, access="write")


def _resolve_read(path: str) -> Path:
    return resolve_allowed_path(path, access="read")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _backup(path: Path) -> str | None:
    if not path.exists():
        return None
    backup_path = path.with_suffix(path.suffix + f".bak.{int(time.time())}")
    backup_path.write_text(_read(path), encoding="utf-8")
    return str(backup_path)


def register(mcp) -> None:
    """Register code editing tools."""

    @mcp.tool()
    def view_file_content(file_path: str, max_chars: int = 80_000) -> dict:
        """Read a text file for editing context."""
        try:
            path = _resolve_read(file_path)
            max_chars = min(max(1_000, max_chars), load_policy().max_file_read_chars)
        except PolicyError as exc:
            audit("code_editing.view_file_content", False, {"path": file_path, "error": exc.code})
            return policy_error_result(exc)

        if not path.exists():
            audit("code_editing.view_file_content", False, {"path": str(path), "error": "file_not_found"})
            return {"success": False, "error": "file_not_found", "path": str(path)}
        if path.is_dir():
            audit("code_editing.view_file_content", False, {"path": str(path), "error": "is_directory"})
            return {"success": False, "error": "is_directory", "path": str(path)}

        content = _read(path)
        audit("code_editing.view_file_content", True, {"path": str(path), "truncated": len(content) > max_chars})
        return {
            "success": True,
            "path": str(path),
            "truncated": len(content) > max_chars,
            "content": content[:max_chars],
        }

    @mcp.tool()
    def write_file(file_path: str, content: str, overwrite: bool = True, create_backup: bool = True) -> dict:
        """Create or replace a UTF-8 text file."""
        try:
            path = _resolve(file_path)
        except PolicyError as exc:
            audit("code_editing.write_file", False, {"path": file_path, "error": exc.code})
            return policy_error_result(exc)
        if path.exists() and path.is_dir():
            audit("code_editing.write_file", False, {"path": str(path), "error": "is_directory"})
            return {"success": False, "error": "is_directory", "path": str(path)}
        if path.exists() and not overwrite:
            audit("code_editing.write_file", False, {"path": str(path), "error": "file_exists"})
            return {"success": False, "error": "file_exists", "path": str(path)}

        backup_path = _backup(path) if create_backup and path.exists() else None
        _write(path, content)
        audit("code_editing.write_file", True, {"path": str(path), "backup_path": backup_path, "bytes": len(content.encode("utf-8"))})
        return {"success": True, "path": str(path), "backup_path": backup_path, "bytes": len(content.encode("utf-8"))}

    @mcp.tool()
    def edit_file_specific(
        file_path: str,
        target_block: str,
        new_block: str,
        replace_all: bool = False,
        create_backup: bool = True,
    ) -> dict:
        """Replace an exact text block in a file."""
        try:
            path = _resolve(file_path)
        except PolicyError as exc:
            audit("code_editing.edit_file_specific", False, {"path": file_path, "error": exc.code})
            return policy_error_result(exc)
        if not path.exists():
            audit("code_editing.edit_file_specific", False, {"path": str(path), "error": "file_not_found"})
            return {"success": False, "error": "file_not_found", "path": str(path)}
        if path.is_dir():
            audit("code_editing.edit_file_specific", False, {"path": str(path), "error": "is_directory"})
            return {"success": False, "error": "is_directory", "path": str(path)}
        if not target_block:
            audit("code_editing.edit_file_specific", False, {"path": str(path), "error": "empty_target_block"})
            return {"success": False, "error": "empty_target_block"}

        content = _read(path)
        count = content.count(target_block)
        if count == 0:
            audit("code_editing.edit_file_specific", False, {"path": str(path), "error": "target_not_found"})
            return {"success": False, "error": "target_not_found", "path": str(path)}
        if count > 1 and not replace_all:
            audit("code_editing.edit_file_specific", False, {"path": str(path), "error": "target_not_unique", "count": count})
            return {"success": False, "error": "target_not_unique", "count": count, "path": str(path)}

        updated = content.replace(target_block, new_block) if replace_all else content.replace(target_block, new_block, 1)
        backup_path = _backup(path) if create_backup else None
        _write(path, updated)

        diff = "\n".join(
            difflib.unified_diff(
                content.splitlines(),
                updated.splitlines(),
                fromfile=f"{path.name}:before",
                tofile=f"{path.name}:after",
                lineterm="",
            )
        )
        audit("code_editing.edit_file_specific", True, {"path": str(path), "replacements": count if replace_all else 1, "backup_path": backup_path})
        return {"success": True, "path": str(path), "replacements": count if replace_all else 1, "backup_path": backup_path, "diff": diff}

    @mcp.tool()
    def inspect_diff(file_path: str, proposed_content: str) -> dict:
        """Preview a unified diff without writing."""
        try:
            path = _resolve(file_path)
        except PolicyError as exc:
            audit("code_editing.inspect_diff", False, {"path": file_path, "error": exc.code})
            return policy_error_result(exc)
        current = _read(path) if path.exists() and path.is_file() else ""
        diff = "\n".join(
            difflib.unified_diff(
                current.splitlines(),
                proposed_content.splitlines(),
                fromfile=f"{path.name}:current",
                tofile=f"{path.name}:proposed",
                lineterm="",
            )
        )
        audit("code_editing.inspect_diff", True, {"path": str(path)})
        return {"success": True, "path": str(path), "diff": diff}

    @mcp.tool()
    def format_code(command: str, cwd: str | None = None, timeout_seconds: int = 60) -> dict:
        """Run a formatter command. Intended for allowlisted local formatter commands."""
        return _run_command(command, cwd, timeout_seconds, "code_editing.format_code")

    @mcp.tool()
    def run_tests(command: str, cwd: str | None = None, timeout_seconds: int = 120) -> dict:
        """Run a test command and return stdout/stderr."""
        return _run_command(command, cwd, timeout_seconds, "code_editing.run_tests")


def _run_command(command: str, cwd: str | None, timeout_seconds: int, action: str) -> dict:
    try:
        tokens = assert_command_allowed(command)
        cwd_path = resolve_allowed_path(cwd, access="execute") if cwd else None
    except PolicyError as exc:
        audit(action, False, {"command": command, "cwd": cwd, "error": exc.code})
        return policy_error_result(exc)

    if cwd_path and not cwd_path.exists():
        audit(action, False, {"command": command, "cwd": str(cwd_path), "error": "cwd_not_found"})
        return {"success": False, "error": "cwd_not_found", "cwd": str(cwd_path)}

    timeout_seconds = min(max(1, timeout_seconds), 600)
    try:
        result = subprocess.run(
            tokens,
            cwd=str(cwd_path) if cwd_path else None,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
        audit(action, result.returncode == 0, {"command": command, "cwd": str(cwd_path) if cwd_path else None, "returncode": result.returncode})
        return {
            "success": result.returncode == 0,
            "command": command,
            "cwd": str(cwd_path) if cwd_path else None,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        audit(action, False, {"command": command, "cwd": str(cwd_path) if cwd_path else None, "error": "timeout"})
        return {"success": False, "error": "timeout", "command": command, "timeout_seconds": timeout_seconds, "stdout": exc.stdout, "stderr": exc.stderr}
