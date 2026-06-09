"""System MCP tools."""

from __future__ import annotations

import datetime as _dt
import locale
import os
import platform
import shutil
import string
import subprocess
import time
from pathlib import Path

from security import PolicyError, assert_command_allowed, audit, load_policy, policy_error_result, resolve_allowed_path


def _resolve(path: str) -> Path:
    return resolve_allowed_path(path, access="execute")


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, str):
        return data
    for encoding in (locale.getpreferredencoding(False), "utf-8", "cp874"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def register(mcp) -> None:
    """Register system tools."""

    @mcp.tool()
    def get_environment() -> dict:
        """Return runtime and OS information."""
        return {
            "success": True,
            "platform": platform.platform(),
            "system": platform.system(),
            "python": platform.python_version(),
            "cwd": str(Path.cwd()),
            "timezone": _dt.datetime.now().astimezone().tzname(),
        }

    @mcp.tool()
    def get_system_drives() -> dict:
        """List available Windows drives or Unix root hints."""
        if os.name == "nt":
            drives = [f"{letter}:\\" for letter in string.ascii_uppercase if Path(f"{letter}:\\").exists()]
            return {"success": True, "platform": "windows", "drives": drives}
        return {"success": True, "platform": "unix", "roots": ["/"]}

    @mcp.tool()
    def check_command(command: str) -> dict:
        """Check whether an executable exists on PATH."""
        executable = command.split()[0] if command.strip() else ""
        found = shutil.which(executable) if executable else None
        try:
            assert_command_allowed(command)
            allowed = True
            error = None
        except PolicyError as exc:
            allowed = False
            error = exc.code
        return {"success": bool(found) and allowed, "command": command, "executable": executable, "path": found, "allowed": allowed, "policy_error": error}

    @mcp.tool()
    def run_command(command: str, cwd: str | None = None, timeout_seconds: int = 30, max_output_chars: int = 30_000) -> dict:
        """Run a shell command with timeout and captured output."""
        try:
            tokens = assert_command_allowed(command)
            cwd_path = _resolve(cwd) if cwd else None
        except PolicyError as exc:
            audit("system.run_command", False, {"command": command, "cwd": cwd, "error": exc.code})
            return policy_error_result(exc)

        timeout_seconds = min(max(1, timeout_seconds), 600)
        max_output_chars = min(max(1_000, max_output_chars), load_policy().max_command_output_chars)

        if cwd_path and not cwd_path.exists():
            audit("system.run_command", False, {"command": command, "cwd": str(cwd_path), "error": "cwd_not_found"})
            return {"success": False, "error": "cwd_not_found", "cwd": str(cwd_path)}

        try:
            result = subprocess.run(
                tokens,
                shell=False,
                cwd=str(cwd_path) if cwd_path else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
            )
            stdout = _decode(result.stdout)
            stderr = _decode(result.stderr)
            audit("system.run_command", result.returncode == 0, {"command": command, "cwd": str(cwd_path) if cwd_path else None, "returncode": result.returncode})
            return {
                "success": result.returncode == 0,
                "command": command,
                "cwd": str(cwd_path) if cwd_path else None,
                "returncode": result.returncode,
                "stdout": stdout[:max_output_chars],
                "stderr": stderr[:max_output_chars],
                "stdout_truncated": len(stdout) > max_output_chars,
                "stderr_truncated": len(stderr) > max_output_chars,
            }
        except subprocess.TimeoutExpired as exc:
            audit("system.run_command", False, {"command": command, "cwd": str(cwd_path) if cwd_path else None, "error": "timeout"})
            return {
                "success": False,
                "error": "timeout",
                "command": command,
                "timeout_seconds": timeout_seconds,
                "stdout": _decode(exc.stdout),
                "stderr": _decode(exc.stderr),
            }

    @mcp.tool()
    def get_current_datetime() -> dict:
        """Return local date, time, weekday, and timezone."""
        now = _dt.datetime.now().astimezone()
        return {
            "success": True,
            "iso": now.isoformat(timespec="seconds"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timezone": now.tzname(),
            "utc_offset": now.strftime("%z"),
        }

    @mcp.tool()
    def generate_efficiency_report(project_name: str, score: float, summary_text: str, output_dir: str) -> dict:
        """Write a Markdown efficiency report."""
        try:
            out_dir = resolve_allowed_path(output_dir, access="write")
        except PolicyError as exc:
            audit("system.generate_efficiency_report", False, {"output_dir": output_dir, "error": exc.code})
            return policy_error_result(exc)
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / f"efficiency_report_{int(time.time())}.md"
        content = f"""# Efficiency Report: {project_name}

Generated: {_dt.datetime.now().isoformat(timespec="seconds")}
Score: {score}/100

## Summary

{summary_text}

## Runtime

- Engine: Model Context Protocol (MCP)
- Transport: stdio
- Server: AI Desk Tools
"""
        target.write_text(content, encoding="utf-8")
        audit("system.generate_efficiency_report", True, {"path": str(target)})
        return {"success": True, "path": str(target)}

    @mcp.tool()
    def health_check() -> dict:
        """Return MCP server health."""
        return {"success": True, "ok": True, "server": "AI Desk Tools"}
