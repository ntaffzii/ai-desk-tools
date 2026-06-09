"""Lightweight vector-like memory search without external embeddings."""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path

from security import PolicyError, TOOLS_ROOT, policy_error_result, resolve_allowed_path


DEFAULT_MEMORY_PATH = TOOLS_ROOT / "memory" / "context_memories.jsonl"


def _tokens(text: str) -> Counter:
    return Counter(token.lower() for token in re.findall(r"[A-Za-z0-9_ก-๙]+", text) if len(token) >= 2)


def _cosine(a: Counter, b: Counter) -> float:
    common = set(a) & set(b)
    numerator = sum(a[t] * b[t] for t in common)
    denom = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return numerator / denom if denom else 0.0


def _memory_path(path: str | None, access: str = "read") -> Path:
    return resolve_allowed_path(path or DEFAULT_MEMORY_PATH, access=access)


def _read_memories(path: Path) -> list[dict]:
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


def register(mcp) -> None:
    """Register vector-memory tools."""

    @mcp.tool()
    def build_vector_memory_index(memory_path: str | None = None) -> dict:
        """Build a lightweight lexical vector index from memory JSONL."""
        try:
            path = _memory_path(memory_path)
            items = _read_memories(path)
        except PolicyError as exc:
            return policy_error_result(exc)
        vectors = []
        for item in items:
            text = " ".join([str(item.get("text", "")), " ".join(item.get("tags", [])), str(item.get("type", "")), str(item.get("file_path", ""))])
            vectors.append({"id": item.get("id"), "type": item.get("type", "note"), "text": item.get("text", ""), "tokens": dict(_tokens(text))})
        return {"success": True, "path": str(path), "count": len(vectors), "index": vectors}

    @mcp.tool()
    def search_vector_memory(query: str, memory_path: str | None = None, limit: int = 10) -> dict:
        """Search memories by cosine similarity over lexical vectors."""
        if not query.strip():
            return {"success": False, "error": "empty_query"}
        try:
            path = _memory_path(memory_path)
            items = _read_memories(path)
        except PolicyError as exc:
            return policy_error_result(exc)
        query_vec = _tokens(query)
        scored = []
        for item in items:
            text = " ".join([str(item.get("text", "")), " ".join(item.get("tags", [])), str(item.get("type", "")), str(item.get("file_path", ""))])
            score = _cosine(query_vec, _tokens(text))
            if score > 0:
                scored.append({**item, "score": score})
        scored.sort(key=lambda item: (-item["score"], item.get("ts", "")))
        safe_limit = max(1, min(int(limit), 50))
        return {"success": True, "path": str(path), "query": query, "count": len(scored[:safe_limit]), "matches": scored[:safe_limit]}

    @mcp.tool()
    def find_related_memories(memory_id: str, memory_path: str | None = None, limit: int = 10) -> dict:
        """Find memories related to one memory id."""
        try:
            path = _memory_path(memory_path)
            items = _read_memories(path)
        except PolicyError as exc:
            return policy_error_result(exc)
        target = next((item for item in items if item.get("id") == memory_id), None)
        if not target:
            return {"success": False, "error": "memory_not_found", "memory_id": memory_id}
        return search_vector_memory(str(target.get("text", "")), str(path), limit)

    @mcp.tool()
    def summarize_memory_clusters(memory_path: str | None = None) -> dict:
        """Summarize memory clusters by type and tags."""
        try:
            path = _memory_path(memory_path)
            items = _read_memories(path)
        except PolicyError as exc:
            return policy_error_result(exc)
        types = Counter(item.get("type", "note") for item in items)
        tags = Counter(tag for item in items for tag in item.get("tags", []))
        return {"success": True, "path": str(path), "total": len(items), "types": dict(types), "top_tags": tags.most_common(20)}
