"""Typed memory and lightweight local context tools."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from security import PolicyError, TOOLS_ROOT, audit, policy_error_result, resolve_allowed_path


MEMORY_CONTEXT_PATH = TOOLS_ROOT / "memory" / "context_memories.jsonl"
VALID_TYPES = {"decision", "preference", "bug", "architecture", "handoff", "note"}


def _path(path: str | None = None, access: str = "read") -> Path:
    target = Path(path).resolve() if path else MEMORY_CONTEXT_PATH
    return resolve_allowed_path(target, access=access)


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                items.append(item)
        except json.JSONDecodeError:
            continue
    return items


def _save(item: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(item, ensure_ascii=False) + "\n")


def _entry(memory_type: str, text: str, tags: str = "", file_path: str = "") -> dict:
    clean_type = memory_type.strip().lower()
    if clean_type not in VALID_TYPES:
        clean_type = "note"
    return {
        "id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "type": clean_type,
        "text": text,
        "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
        "file_path": file_path,
    }


def register(mcp) -> None:
    """Register typed memory/context tools."""

    @mcp.tool()
    def save_project_decision(text: str, tags: str = "", file_path: str = "", memory_path: str | None = None) -> dict:
        """Save a durable project decision."""
        return save_typed_memory("decision", text, tags, file_path, memory_path)

    @mcp.tool()
    def save_user_preference(text: str, tags: str = "", memory_path: str | None = None) -> dict:
        """Save a user preference."""
        return save_typed_memory("preference", text, tags, "", memory_path)

    @mcp.tool()
    def save_bug_lesson(text: str, tags: str = "", file_path: str = "", memory_path: str | None = None) -> dict:
        """Save a debugging lesson or root cause."""
        return save_typed_memory("bug", text, tags, file_path, memory_path)

    @mcp.tool()
    def save_typed_memory(memory_type: str, text: str, tags: str = "", file_path: str = "", memory_path: str | None = None) -> dict:
        """Save typed local memory."""
        try:
            target = _path(memory_path, "write")
            item = _entry(memory_type, text, tags, file_path)
            _save(item, target)
        except PolicyError as exc:
            audit("memory_context.save_typed_memory", False, {"error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            return {"success": False, "error": "memory_write_failed", "message": str(exc)}
        audit("memory_context.save_typed_memory", True, {"path": str(target), "id": item["id"], "type": item["type"]})
        return {"success": True, "path": str(target), "memory": item}

    @mcp.tool()
    def search_project_context(query: str, memory_type: str = "", memory_path: str | None = None, limit: int = 50) -> dict:
        """Search typed memories by text, tags, type, or linked file."""
        try:
            target = _path(memory_path)
            items = _read(target)
        except PolicyError as exc:
            return policy_error_result(exc)
        needle = query.lower()
        clean_type = memory_type.strip().lower()
        matches = []
        for item in items:
            if clean_type and item.get("type") != clean_type:
                continue
            haystack = " ".join([item.get("text", ""), item.get("file_path", ""), " ".join(item.get("tags", [])), item.get("type", "")]).lower()
            if needle in haystack:
                matches.append(item)
        selected = matches[-max(1, min(int(limit), 200)) :]
        return {"success": True, "path": str(target), "query": query, "count": len(selected), "matches": selected}

    @mcp.tool()
    def build_context_pack(query: str = "", memory_path: str | None = None, limit: int = 30) -> dict:
        """Build a compact memory context pack for an agent turn."""
        try:
            target = _path(memory_path)
            items = _read(target)
        except PolicyError as exc:
            return policy_error_result(exc)
        if query:
            needle = query.lower()
            items = [item for item in items if needle in json.dumps(item, ensure_ascii=False).lower()]
        selected = items[-max(1, min(int(limit), 100)) :]
        grouped: dict[str, list[dict]] = {}
        for item in selected:
            grouped.setdefault(item.get("type", "note"), []).append(item)
        return {"success": True, "path": str(target), "query": query, "count": len(selected), "groups": grouped}

    @mcp.tool()
    def compact_old_memories(memory_path: str | None = None, keep_recent: int = 100) -> dict:
        """Plan memory compaction without deleting anything."""
        try:
            target = _path(memory_path)
            items = _read(target)
        except PolicyError as exc:
            return policy_error_result(exc)
        keep_recent = max(1, min(int(keep_recent), 1000))
        old = items[:-keep_recent] if len(items) > keep_recent else []
        return {
            "success": True,
            "path": str(target),
            "total": len(items),
            "would_compact": len(old),
            "kept_recent": min(len(items), keep_recent),
            "recommendation": "Summarize old memories into a handoff note, then save it as type=handoff.",
        }

    @mcp.tool()
    def generate_handoff_from_memory(memory_path: str | None = None, limit: int = 50) -> dict:
        """Generate a handoff-style text block from recent memory."""
        pack = build_context_pack("", memory_path, limit)
        if not pack.get("success"):
            return pack
        lines = ["# Memory Handoff", ""]
        for memory_type, items in pack.get("groups", {}).items():
            lines.append(f"## {memory_type.title()}")
            for item in items:
                file_ref = f" ({item.get('file_path')})" if item.get("file_path") else ""
                lines.append(f"- {item.get('text', '')}{file_ref}")
            lines.append("")
        return {"success": True, "path": pack.get("path"), "handoff": "\n".join(lines).strip()}
