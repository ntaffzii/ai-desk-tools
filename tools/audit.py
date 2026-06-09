"""Audit log inspection MCP tools."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from security import audit, load_policy


def _audit_log_path() -> Path:
    return load_policy().audit_log


def _read_events(limit: int = 200) -> list[dict[str, Any]]:
    path = _audit_log_path()
    if not path.exists():
        return []

    limit = min(max(1, limit), 5_000)
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    selected = lines[-limit:]
    events: list[dict[str, Any]] = []
    for line in selected:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            event = {"ts": "", "action": "audit.parse_error", "success": False, "details": {"raw": line[:500]}}
        events.append(event)
    return events


def _filter_events(
    events: list[dict[str, Any]],
    action_contains: str = "",
    success: bool | None = None,
    error_contains: str = "",
) -> list[dict[str, Any]]:
    filtered = events
    if action_contains:
        needle = action_contains.lower()
        filtered = [event for event in filtered if needle in str(event.get("action", "")).lower()]
    if success is not None:
        filtered = [event for event in filtered if bool(event.get("success")) is success]
    if error_contains:
        needle = error_contains.lower()
        filtered = [
            event
            for event in filtered
            if needle in str(event.get("details", {}).get("error", "")).lower()
            or needle in json.dumps(event.get("details", {}), ensure_ascii=False).lower()
        ]
    return filtered


def register(mcp) -> None:
    """Register audit log tools."""

    @mcp.tool()
    def get_audit_log_info() -> dict:
        """Return audit log path and basic file metadata."""
        path = _audit_log_path()
        exists = path.exists()
        stat = path.stat() if exists else None
        audit("audit.get_audit_log_info", True, {"path": str(path), "exists": exists})
        return {
            "success": True,
            "path": str(path),
            "exists": exists,
            "size_bytes": stat.st_size if stat else 0,
            "line_count": len(path.read_text(encoding="utf-8", errors="replace").splitlines()) if exists else 0,
        }

    @mcp.tool()
    def read_audit_log(limit: int = 100, action_contains: str = "", success: bool | None = None) -> dict:
        """Read recent audit events, optionally filtered by action or success."""
        events = _filter_events(_read_events(limit), action_contains=action_contains, success=success)
        audit(
            "audit.read_audit_log",
            True,
            {"limit": limit, "action_contains": action_contains, "success_filter": success, "result_count": len(events)},
        )
        return {"success": True, "count": len(events), "events": events}

    @mcp.tool()
    def summarize_audit_log(limit: int = 500) -> dict:
        """Summarize recent audit events by action, success, and error code."""
        events = _read_events(limit)
        action_counts = Counter(str(event.get("action", "")) for event in events)
        success_counts = Counter("success" if event.get("success") else "failure" for event in events)
        error_counts = Counter(
            str(event.get("details", {}).get("error", ""))
            for event in events
            if not event.get("success") and event.get("details", {}).get("error")
        )
        audit("audit.summarize_audit_log", True, {"limit": limit, "event_count": len(events)})
        return {
            "success": True,
            "event_count": len(events),
            "by_action": dict(action_counts.most_common(25)),
            "by_result": dict(success_counts),
            "by_error": dict(error_counts.most_common(25)),
            "latest": events[-1] if events else None,
        }

    @mcp.tool()
    def find_policy_denials(limit: int = 500) -> dict:
        """Return recent failed audit events that look like policy denials."""
        denial_error_codes = {
            "path_outside_allowed_roots",
            "shell_control_operator_blocked",
            "blocked_executable",
            "command_not_allowlisted",
            "invalid_command",
            "empty_command",
        }
        events = _read_events(limit)
        denials = [
            event
            for event in events
            if not event.get("success") and str(event.get("details", {}).get("error", "")) in denial_error_codes
        ]
        audit("audit.find_policy_denials", True, {"limit": limit, "denial_count": len(denials)})
        return {"success": True, "count": len(denials), "denials": denials}

    @mcp.tool()
    def find_audit_events(action_contains: str = "", error_contains: str = "", limit: int = 500) -> dict:
        """Search recent audit events by action text or error/detail text."""
        events = _filter_events(_read_events(limit), action_contains=action_contains, error_contains=error_contains)
        audit(
            "audit.find_audit_events",
            True,
            {"action_contains": action_contains, "error_contains": error_contains, "limit": limit, "result_count": len(events)},
        )
        return {"success": True, "count": len(events), "events": events}
