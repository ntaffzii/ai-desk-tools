"""Provider-neutral RAG planning and chunking tools."""

from __future__ import annotations

import hashlib
import json
import os
import re


def _chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    if not clean:
        return []
    size = max(200, min(int(chunk_size), 4000))
    step = max(50, size - max(0, min(int(overlap), size // 2)))
    return [clean[index:index + size] for index in range(0, len(clean), step)]


def register(mcp) -> None:
    """Register RAG adapter tools."""

    @mcp.tool()
    def list_rag_providers() -> dict:
        """List supported RAG provider patterns."""
        return {
            "success": True,
            "providers": [
                {"id": "local-lightweight", "status": "available", "notes": "Uses local lexical scoring such as vector-memory."},
                {"id": "openai-compatible-embeddings", "status": "planned_by_env", "env": ["EMBEDDINGS_API_URL", "EMBEDDINGS_MODEL", "EMBEDDINGS_API_KEY"]},
                {"id": "chroma", "status": "planned_optional", "env": ["CHROMA_PATH", "CHROMA_URL"]},
                {"id": "sqlite-vss", "status": "planned_optional", "env": ["RAG_SQLITE_PATH"]},
            ],
        }

    @mcp.tool()
    def check_rag_config() -> dict:
        """Check configured RAG/embedding env keys."""
        keys = ["EMBEDDINGS_API_URL", "EMBEDDINGS_MODEL", "EMBEDDINGS_API_KEY", "CHROMA_PATH", "CHROMA_URL", "RAG_SQLITE_PATH"]
        return {"success": True, "configured": [key for key in keys if os.getenv(key)]}

    @mcp.tool()
    def chunk_text_for_rag(text: str, source_id: str = "inline", chunk_size: int = 1200, overlap: int = 120) -> dict:
        """Split text into stable RAG chunks."""
        parts = _chunks(text, chunk_size, overlap)
        chunks = []
        for index, part in enumerate(parts):
            digest = hashlib.sha256(f"{source_id}:{index}:{part}".encode("utf-8")).hexdigest()[:16]
            chunks.append({"id": digest, "source_id": source_id, "index": index, "text": part})
        return {"success": True, "source_id": source_id, "count": len(chunks), "chunks": chunks}

    @mcp.tool()
    def plan_rag_index(source_paths_json: str, provider: str = "local-lightweight") -> dict:
        """Plan a RAG index build from source paths without executing it."""
        try:
            paths = json.loads(source_paths_json)
            if not isinstance(paths, list):
                return {"success": False, "error": "source_paths_must_be_list"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_source_paths_json", "message": str(exc)}
        return {"success": True, "mode": "plan_only", "provider": provider, "sources": paths, "steps": ["Validate allowed roots", "Read text sources", "Chunk with stable ids", "Embed or score chunks", "Store metadata with source path and timestamp", "Search before answering"]}

    @mcp.tool()
    def build_embedding_request_plan(texts_json: str, provider: str = "openai-compatible-embeddings") -> dict:
        """Create an embedding request payload plan without calling an embedding provider."""
        try:
            texts = json.loads(texts_json)
            if not isinstance(texts, list):
                return {"success": False, "error": "texts_must_be_list"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_texts_json", "message": str(exc)}
        return {
            "success": True,
            "mode": "plan_only",
            "provider": provider,
            "endpoint_env": "EMBEDDINGS_API_URL",
            "payload": {"model": os.getenv("EMBEDDINGS_MODEL", "text-embedding-3-small"), "input": texts[:100]},
        }

