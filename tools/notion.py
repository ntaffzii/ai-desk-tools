"""Notion API planning and read tools."""

from __future__ import annotations

import json
import os
import urllib.request


NOTION_VERSION = "2022-06-28"


def _token() -> str:
    return os.getenv("NOTION_TOKEN") or os.getenv("NOTION_API_KEY") or ""


def _request(path: str, payload: dict | None = None, method: str = "POST") -> dict:
    token = _token()
    if not token:
        return {"success": False, "error": "notion_token_missing", "message": "Set NOTION_TOKEN."}
    data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"https://api.notion.com/v1{path}",
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {token}", "Notion-Version": NOTION_VERSION, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read(5_000_000).decode("utf-8", errors="replace"))


def register(mcp) -> None:
    """Register Notion tools."""

    @mcp.tool()
    def check_notion_auth() -> dict:
        """Check whether Notion token is configured."""
        return {"success": True, "configured": bool(_token()), "env_keys": [key for key in ["NOTION_TOKEN", "NOTION_API_KEY"] if os.getenv(key)]}

    @mcp.tool()
    def search_notion_pages(query: str, page_size: int = 10) -> dict:
        """Search Notion pages when token is configured."""
        try:
            data = _request("/search", {"query": query, "page_size": max(1, min(int(page_size), 25))})
        except Exception as exc:
            return {"success": False, "error": "notion_search_failed", "message": str(exc)}
        if data.get("success") is False:
            return data
        return {"success": True, "query": query, "results": [{"id": item.get("id"), "object": item.get("object"), "url": item.get("url")} for item in data.get("results", [])]}

    @mcp.tool()
    def read_notion_page(page_id: str) -> dict:
        """Read Notion page metadata when token is configured."""
        try:
            data = _request(f"/pages/{page_id}", None, "GET")
        except Exception as exc:
            return {"success": False, "error": "notion_page_failed", "message": str(exc), "page_id": page_id}
        if data.get("success") is False:
            return data
        return {"success": True, "page": data}

    @mcp.tool()
    def create_notion_note_plan(parent_page_id: str, title: str, content: str) -> dict:
        """Plan a Notion note creation payload without sending it."""
        payload = {"parent": {"page_id": parent_page_id}, "properties": {"title": {"title": [{"text": {"content": title}}]}}, "children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:1800]}}]}}]}
        return {"success": True, "payload": payload}

    @mcp.tool()
    def append_notion_block_plan(page_id: str, content: str) -> dict:
        """Plan an append-block payload without sending it."""
        payload = {"children": [{"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": content[:1800]}}]}}]}
        return {"success": True, "page_id": page_id, "payload": payload}
