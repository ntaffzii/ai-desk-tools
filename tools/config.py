"""Configuration inspection MCP tools."""

from __future__ import annotations

import os
import re
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next"}
CONFIG_SUFFIXES = {".env", ".ini", ".toml", ".yaml", ".yml", ".json", ".js", ".ts", ".py"}
SECRET_WORDS = ("secret", "token", "password", "passwd", "private_key", "api_key", "apikey", "credential")
ENV_KEY_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$")


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 6, max_file_size: int = 500_000):
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            path = current / name
            lowered = name.lower()
            try:
                if path.stat().st_size > max_file_size:
                    continue
            except OSError:
                continue
            if lowered.startswith(".env") or "config" in lowered or path.suffix.lower() in CONFIG_SUFFIXES:
                yield path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _redact_value(value: str) -> str:
    value = value.strip().strip('"').strip("'")
    if not value:
        return ""
    return f"<redacted:{len(value)} chars>"


def register(mcp) -> None:
    """Register configuration tools."""

    @mcp.tool()
    def find_config_files(project_path: str | None = None, max_depth: int = 6, limit: int = 120) -> dict:
        """Find likely configuration files."""
        try:
            root = _resolve_project(project_path)
            files = []
            for path in _iter_files(root, max_depth=max_depth):
                files.append({"path": str(path), "relative_path": str(path.relative_to(root)), "size_bytes": path.stat().st_size})
                if len(files) >= max(1, min(int(limit), 300)):
                    break
        except PolicyError as exc:
            audit("config.find_config_files", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        audit("config.find_config_files", True, {"project_path": str(root), "count": len(files)})
        return {"success": True, "project_path": str(root), "count": len(files), "files": files}

    @mcp.tool()
    def list_env_keys(project_path: str | None = None, max_depth: int = 6, limit: int = 200) -> dict:
        """List environment variable keys referenced in config/source files."""
        try:
            root = _resolve_project(project_path)
            keys: dict[str, set[str]] = {}
            for path in _iter_files(root, max_depth=max_depth):
                try:
                    content = _read(path)
                except OSError:
                    continue
                found = set(ENV_KEY_RE.findall(content))
                if found:
                    keys[str(path.relative_to(root))] = found
                if sum(len(value) for value in keys.values()) >= limit:
                    break
        except PolicyError as exc:
            audit("config.list_env_keys", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        flattened = sorted({key for values in keys.values() for key in values})[: max(1, min(int(limit), 500))]
        result = {"success": True, "project_path": str(root), "count": len(flattened), "keys": flattened, "files": {file: sorted(values) for file, values in keys.items()}}
        audit("config.list_env_keys", True, {"project_path": str(root), "count": len(flattened)})
        return result

    @mcp.tool()
    def inspect_env_example(project_path: str | None = None, include_values: bool = False) -> dict:
        """Inspect .env.example-style files with value redaction by default."""
        try:
            root = _resolve_project(project_path)
            examples = []
            for path in _iter_files(root):
                if not path.name.lower().startswith(".env"):
                    continue
                entries = []
                for line in _read(path).splitlines():
                    match = ASSIGNMENT_RE.match(line)
                    if match:
                        value = match.group(2).strip() if include_values else _redact_value(match.group(2))
                        entries.append({"key": match.group(1), "value": value})
                examples.append({"path": str(path), "relative_path": str(path.relative_to(root)), "entries": entries})
        except PolicyError as exc:
            audit("config.inspect_env_example", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        audit("config.inspect_env_example", True, {"project_path": str(root), "count": len(examples)})
        return {"success": True, "project_path": str(root), "count": len(examples), "examples": examples}

    @mcp.tool()
    def check_secret_hygiene(project_path: str | None = None, max_depth: int = 6) -> dict:
        """Flag likely secret-bearing config keys without returning secret values."""
        try:
            root = _resolve_project(project_path)
            findings = []
            for path in _iter_files(root, max_depth=max_depth):
                try:
                    lines = _read(path).splitlines()
                except OSError:
                    continue
                for index, line in enumerate(lines, 1):
                    lower = line.lower()
                    if any(word in lower for word in SECRET_WORDS):
                        key_match = ASSIGNMENT_RE.match(line)
                        findings.append({"file": str(path), "relative_file": str(path.relative_to(root)), "line": index, "key": key_match.group(1) if key_match else None})
        except PolicyError as exc:
            audit("config.check_secret_hygiene", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        audit("config.check_secret_hygiene", True, {"project_path": str(root), "count": len(findings)})
        return {"success": True, "project_path": str(root), "count": len(findings), "findings": findings}

    @mcp.tool()
    def summarize_config_surface(project_path: str | None = None) -> dict:
        """Summarize config files, env keys, and secret hygiene signals."""
        files = find_config_files(project_path)
        keys = list_env_keys(project_path)
        secrets = check_secret_hygiene(project_path)
        success = files.get("success") and keys.get("success") and secrets.get("success")
        return {
            "success": bool(success),
            "project_path": files.get("project_path"),
            "config_file_count": files.get("count", 0),
            "env_key_count": keys.get("count", 0),
            "secret_signal_count": secrets.get("count", 0),
            "warnings": [] if files.get("count", 0) else ["No likely config files found"],
        }
