"""Shared security policy for MCP tools.

This module centralizes filesystem, command, and audit behavior so individual
tools do not each invent their own safety rules.
"""

from __future__ import annotations

import json
import os
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOOLS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_ROOT.parent
POLICY_PATH = TOOLS_ROOT / "config" / "tool_policy.json"


class PolicyError(Exception):
    """Raised when an action violates the configured tool policy."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class ToolPolicy:
    allowed_roots: tuple[Path, ...]
    audit_log: Path
    max_file_read_chars: int
    max_command_output_chars: int
    allow_shell_control_operators: bool
    allowed_command_prefixes: tuple[tuple[str, ...], ...]
    blocked_executables: tuple[str, ...]


def _load_raw_policy() -> dict[str, Any]:
    if not POLICY_PATH.exists():
        return {}
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def _expand_path(raw: str) -> Path:
    expanded = raw.replace("${REPO_ROOT}", str(REPO_ROOT)).replace("${TOOLS_ROOT}", str(TOOLS_ROOT))
    expanded = os.path.expandvars(os.path.expanduser(expanded))
    return Path(expanded).resolve()


def load_policy() -> ToolPolicy:
    raw = _load_raw_policy()
    command_policy = raw.get("commands", {})
    allowed_roots = tuple(_expand_path(path) for path in raw.get("allowed_roots", ["${REPO_ROOT}"]))
    audit_log_raw = raw.get("audit_log", "logs/audit.jsonl")
    audit_log_candidate = Path(os.path.expandvars(os.path.expanduser(audit_log_raw)))
    audit_log = audit_log_candidate.resolve() if audit_log_candidate.is_absolute() else (TOOLS_ROOT / audit_log_candidate).resolve()

    return ToolPolicy(
        allowed_roots=allowed_roots,
        audit_log=audit_log,
        max_file_read_chars=int(raw.get("max_file_read_chars", 200_000)),
        max_command_output_chars=int(raw.get("max_command_output_chars", 200_000)),
        allow_shell_control_operators=bool(command_policy.get("allow_shell_control_operators", False)),
        allowed_command_prefixes=tuple(tuple(item) for item in command_policy.get("allowed_prefixes", [])),
        blocked_executables=tuple(str(item).lower() for item in command_policy.get("blocked_executables", [])),
    )


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_allowed_path(path: str | Path, access: str = "read") -> Path:
    """Resolve a path and ensure it stays inside an allowed root."""
    target = Path(path).expanduser().resolve()
    policy = load_policy()
    if any(_is_relative_to(target, root) for root in policy.allowed_roots):
        return target

    raise PolicyError(
        "path_outside_allowed_roots",
        f"{access} access is outside configured allowed roots",
        {
            "path": str(target),
            "allowed_roots": [str(root) for root in policy.allowed_roots],
            "access": access,
        },
    )


def parse_command(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=False)
    except ValueError as exc:
        raise PolicyError("invalid_command", str(exc), {"command": command}) from exc


def assert_command_allowed(command: str) -> list[str]:
    """Validate a command against the configured allowlist."""
    policy = load_policy()
    stripped = command.strip()
    if not stripped:
        raise PolicyError("empty_command", "command is empty")

    control_markers = ("&&", "||", ";", "|", ">", "<", "$(", "`")
    if not policy.allow_shell_control_operators and any(marker in stripped for marker in control_markers):
        raise PolicyError("shell_control_operator_blocked", "shell control operators are blocked", {"command": command})

    tokens = parse_command(stripped)
    if not tokens:
        raise PolicyError("empty_command", "command is empty")

    executable = tokens[0].strip('"').lower()
    if executable in policy.blocked_executables:
        raise PolicyError("blocked_executable", f"executable '{executable}' is blocked", {"command": command})

    normalized = tuple(token.strip('"') for token in tokens)
    for prefix in policy.allowed_command_prefixes:
        if len(normalized) >= len(prefix) and tuple(token.lower() for token in normalized[: len(prefix)]) == tuple(
            token.lower() for token in prefix
        ):
            return tokens

    raise PolicyError(
        "command_not_allowlisted",
        "command does not match an allowed prefix",
        {
            "command": command,
            "allowed_prefixes": [" ".join(prefix) for prefix in policy.allowed_command_prefixes],
        },
    )


def audit(action: str, success: bool, details: dict[str, Any] | None = None) -> None:
    """Append one JSON audit event. Audit failures must not break tools."""
    try:
        policy = load_policy()
        event = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "action": action,
            "success": success,
            "details": details or {},
        }
        policy.audit_log.parent.mkdir(parents=True, exist_ok=True)
        with policy.audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        return


def policy_error_result(exc: PolicyError) -> dict[str, Any]:
    return {"success": False, "error": exc.code, "message": exc.message, **exc.details}
