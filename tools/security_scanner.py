"""Repository security scanning MCP tools."""

from __future__ import annotations

import os
import re
from pathlib import Path

from security import PolicyError, audit, policy_error_result, resolve_allowed_path
from tools import dependency_risk


IGNORED_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".next", ".backups"}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "generic_secret_assignment": re.compile(r"(?i)\b[A-Z0-9_]*(secret|token|password|api[_-]?key)[A-Z0-9_]*\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"),
}
ENV_VALUE_PATTERN = re.compile(r"^\s*([A-Z][A-Z0-9_]{2,})\s*=\s*(.+?)\s*$")
DANGEROUS_COMMAND_PATTERNS = {
    "reset_hard": re.compile(r"\bgit\s+reset\s+--hard\b", re.IGNORECASE),
    "force_push": re.compile(r"\bgit\s+push\b.*\s--force(?:-with-lease)?\b", re.IGNORECASE),
    "recursive_remove": re.compile(r"\b(rm\s+-rf|Remove-Item\b.*-Recurse|del\s+/s)\b", re.IGNORECASE),
    "curl_pipe_shell": re.compile(r"\b(curl|wget)\b.+\|\s*(sh|bash|powershell|pwsh)\b", re.IGNORECASE),
}


def _resolve_project(path: str | None) -> Path:
    root = resolve_allowed_path(path or ".", access="read")
    if not root.exists():
        raise PolicyError("path_not_found", "project path does not exist", {"path": str(root)})
    if not root.is_dir():
        raise PolicyError("path_not_directory", "project path must be a directory", {"path": str(root)})
    return root


def _iter_files(root: Path, max_depth: int = 8, max_file_size: int = 1_000_000):
    for current_root, dirs, files in os.walk(root):
        current = Path(current_root)
        depth = len(current.relative_to(root).parts)
        dirs[:] = [] if depth >= max_depth else [name for name in dirs if name not in IGNORED_DIRS]
        for name in files:
            path = current / name
            try:
                if path.stat().st_size <= max_file_size:
                    yield path
            except OSError:
                continue


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def register(mcp) -> None:
    """Register repository security scanner tools."""

    @mcp.tool()
    def scan_secrets_in_repo(project_path: str | None = None, max_depth: int = 8, limit: int = 200) -> dict:
        """Scan text files for likely secret patterns without returning secret values."""
        try:
            root = _resolve_project(project_path)
            findings = []
            for path in _iter_files(root, max_depth=max_depth):
                try:
                    lines = _read(path).splitlines()
                except OSError:
                    continue
                for line_no, line in enumerate(lines, 1):
                    for kind, pattern in SECRET_PATTERNS.items():
                        if pattern.search(line):
                            findings.append({"file": str(path), "relative_file": str(path.relative_to(root)), "line": line_no, "kind": kind})
                    if len(findings) >= limit:
                        break
                if len(findings) >= limit:
                    break
        except PolicyError as exc:
            audit("security_scanner.scan_secrets_in_repo", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        audit("security_scanner.scan_secrets_in_repo", True, {"project_path": str(root), "count": len(findings)})
        return {"success": True, "project_path": str(root), "count": len(findings), "findings": findings}

    @mcp.tool()
    def scan_dangerous_commands(project_path: str | None = None, max_depth: int = 8, limit: int = 200) -> dict:
        """Scan files for dangerous shell/Git command patterns."""
        try:
            root = _resolve_project(project_path)
            findings = []
            for path in _iter_files(root, max_depth=max_depth):
                try:
                    lines = _read(path).splitlines()
                except OSError:
                    continue
                for line_no, line in enumerate(lines, 1):
                    for kind, pattern in DANGEROUS_COMMAND_PATTERNS.items():
                        if pattern.search(line):
                            findings.append({"file": str(path), "relative_file": str(path.relative_to(root)), "line": line_no, "kind": kind})
                    if len(findings) >= limit:
                        break
                if len(findings) >= limit:
                    break
        except PolicyError as exc:
            audit("security_scanner.scan_dangerous_commands", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(findings), "findings": findings}

    @mcp.tool()
    def scan_env_exposure(project_path: str | None = None, max_depth: int = 6) -> dict:
        """Inspect .env-style files and report keys with non-empty values, values redacted."""
        try:
            root = _resolve_project(project_path)
            findings = []
            for path in _iter_files(root, max_depth=max_depth):
                if not path.name.lower().startswith(".env"):
                    continue
                for line_no, line in enumerate(_read(path).splitlines(), 1):
                    match = ENV_VALUE_PATTERN.match(line)
                    if match and match.group(2).strip():
                        findings.append({"file": str(path), "relative_file": str(path.relative_to(root)), "line": line_no, "key": match.group(1), "value_present": True})
        except PolicyError as exc:
            audit("security_scanner.scan_env_exposure", False, {"project_path": project_path, "error": exc.code})
            return policy_error_result(exc)
        return {"success": True, "project_path": str(root), "count": len(findings), "findings": findings}

    @mcp.tool()
    def scan_dependency_manifest_risks(project_path: str | None = None) -> dict:
        """Reuse offline dependency-risk heuristics for a security report."""
        mcp_like = type("M", (), {"tool": lambda self: (lambda func: func)})()
        tools = {}
        dependency_risk.register(type("Fake", (), {"tool": lambda self: (lambda func: tools.setdefault(func.__name__, func) or func)})())
        unpinned = tools["find_unpinned_dependencies"](project_path)
        risky_names = tools["find_high_risk_dependency_names"](project_path)
        return {
            "success": bool(unpinned.get("success") and risky_names.get("success")),
            "project_path": unpinned.get("project_path") or risky_names.get("project_path"),
            "unpinned_count": unpinned.get("count", 0),
            "high_risk_name_count": risky_names.get("count", 0),
            "unpinned": unpinned.get("findings", []),
            "high_risk_names": risky_names.get("findings", []),
        }

    @mcp.tool()
    def generate_security_report(project_path: str | None = None) -> dict:
        """Generate a compact repository security report."""
        secrets = scan_secrets_in_repo(project_path)
        commands = scan_dangerous_commands(project_path)
        env = scan_env_exposure(project_path)
        deps = scan_dependency_manifest_risks(project_path)
        warnings = []
        if secrets.get("count", 0):
            warnings.append("Potential secrets found")
        if commands.get("count", 0):
            warnings.append("Dangerous command patterns found")
        if env.get("count", 0):
            warnings.append("Environment files contain values; verify they are examples or ignored")
        if deps.get("unpinned_count", 0):
            warnings.append("Unpinned or loosely pinned dependencies found")
        return {
            "success": all(item.get("success") for item in (secrets, commands, env, deps)),
            "project_path": secrets.get("project_path"),
            "summary": {
                "secret_findings": secrets.get("count", 0),
                "dangerous_command_findings": commands.get("count", 0),
                "env_value_findings": env.get("count", 0),
                "dependency_risk_findings": deps.get("unpinned_count", 0) + deps.get("high_risk_name_count", 0),
                "warnings": warnings,
            },
            "sections": {"secrets": secrets, "commands": commands, "env": env, "dependencies": deps},
        }
