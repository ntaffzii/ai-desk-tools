"""Local persistent memory MCP tools."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from security import PolicyError, TOOLS_ROOT, audit, policy_error_result, resolve_allowed_path


MEMORY_PATH = TOOLS_ROOT / "memory" / "memories.jsonl"


def _memory_path(path: str | None = None, access: str = "read") -> Path:
    target = Path(path).resolve() if path else MEMORY_PATH
    return resolve_allowed_path(target, access=access)


def _read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def register(mcp) -> None:
    """Register memory tools."""

    @mcp.tool()
    def save_memory(text: str, tags: str = "", memory_path: str | None = None) -> dict:
        """Save one local memory entry."""
        try:
            path = _memory_path(memory_path, "write")
            path.parent.mkdir(parents=True, exist_ok=True)
            event = {"id": str(uuid.uuid4()), "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "text": text, "tags": [tag.strip() for tag in tags.split(",") if tag.strip()]}
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except PolicyError as exc:
            audit("memory.save_memory", False, {"error": exc.code})
            return policy_error_result(exc)
        except OSError as exc:
            return {"success": False, "error": "memory_write_failed", "message": str(exc)}
        audit("memory.save_memory", True, {"path": str(path), "id": event["id"]})
        return {"success": True, "path": str(path), "memory": event}

    @mcp.tool()
    def list_memories(memory_path: str | None = None, limit: int = 50) -> dict:
        """List recent memories."""
        try:
            path = _memory_path(memory_path)
            events = _read_events(path)[-max(1, min(int(limit), 200)) :]
        except PolicyError as exc:
            return policy_error_result(exc)
        return {"success": True, "path": str(path), "count": len(events), "memories": events}

    @mcp.tool()
    def search_memory(query: str, memory_path: str | None = None, limit: int = 50) -> dict:
        """Search local memory text and tags."""
        result = list_memories(memory_path, 10_000)
        if not result.get("success"):
            return result
        needle = query.lower()
        matches = [item for item in result["memories"] if needle in item.get("text", "").lower() or any(needle in tag.lower() for tag in item.get("tags", []))]
        return {"success": True, "path": result["path"], "query": query, "count": len(matches[:limit]), "matches": matches[:limit]}

    @mcp.tool()
    def summarize_project_memory(memory_path: str | None = None) -> dict:
        """Summarize local memory counts by tag."""
        result = list_memories(memory_path, 10_000)
        if not result.get("success"):
            return result
        counts = {}
        for item in result["memories"]:
            for tag in item.get("tags", []):
                counts[tag] = counts.get(tag, 0) + 1
        return {"success": True, "path": result["path"], "memory_count": result["count"], "counts_by_tag": counts}
