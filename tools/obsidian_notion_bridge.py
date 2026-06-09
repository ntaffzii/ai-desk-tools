"""Planning tools for Obsidian and Notion knowledge handoffs."""

from __future__ import annotations

import json
import re
from pathlib import Path

from security import PolicyError, policy_error_result, resolve_allowed_path


WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)")
TAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_/-]+)")


def _read_text(path: str) -> tuple[Path | None, str | dict]:
    try:
        resolved = resolve_allowed_path(path, access="read")
        if not resolved.exists():
            return None, {"success": False, "error": "file_not_found", "path": str(resolved)}
        if resolved.is_dir():
            return None, {"success": False, "error": "path_is_directory", "path": str(resolved)}
        return resolved, resolved.read_text(encoding="utf-8", errors="replace")
    except PolicyError as exc:
        return None, policy_error_result(exc)


def _title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip() or fallback
    return fallback


def register(mcp) -> None:
    """Register Obsidian-Notion bridge tools."""

    @mcp.tool()
    def inspect_obsidian_note_for_notion(file_path: str) -> dict:
        """Inspect one Obsidian Markdown note and extract Notion-ready metadata."""
        path, result = _read_text(file_path)
        if path is None:
            return result
        text = str(result)
        title = _title_from_markdown(text, path.stem)
        links = sorted(set(WIKILINK_RE.findall(text)))
        tags = sorted(set(TAG_RE.findall(text)))
        return {
            "success": True,
            "path": str(path),
            "title": title,
            "tags": tags,
            "wikilinks": links,
            "excerpt": text[:2000],
            "recommended_notion_properties": {
                "Name": title,
                "Source": "Obsidian",
                "Tags": tags,
                "Original Path": str(path),
            },
        }

    @mcp.tool()
    def plan_obsidian_to_notion(file_path: str, parent_page_id: str | None = None) -> dict:
        """Create a safe Notion page payload plan from an Obsidian Markdown note."""
        inspection = inspect_obsidian_note_for_notion(file_path)
        if not inspection.get("success"):
            return inspection
        children = [
            {"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": inspection["excerpt"][:1800]}}]}},
        ]
        payload = {
            "parent": {"page_id": parent_page_id or "<NOTION_PARENT_PAGE_ID>"},
            "properties": {"title": {"title": [{"text": {"content": inspection["title"]}}]}},
            "children": children,
        }
        return {"success": True, "mode": "plan_only", "source": inspection, "notion_payload": payload}

    @mcp.tool()
    def plan_notion_to_obsidian(page_json: str, vault_folder: str, file_name: str | None = None) -> dict:
        """Create a safe Obsidian Markdown write plan from supplied Notion page JSON."""
        try:
            page = json.loads(page_json)
            if not isinstance(page, dict):
                return {"success": False, "error": "page_json_must_be_object"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_page_json", "message": str(exc)}
        try:
            folder = resolve_allowed_path(vault_folder, access="write")
        except PolicyError as exc:
            return policy_error_result(exc)
        title = str(page.get("title") or page.get("name") or page.get("id") or "notion-note").strip()
        safe_name = file_name or re.sub(r"[^A-Za-z0-9ก-๙_. -]+", "-", title).strip(" .-") or "notion-note"
        if not safe_name.lower().endswith(".md"):
            safe_name += ".md"
        target = folder / safe_name
        content = "\n".join([
            "---",
            "source: notion",
            f"notion_id: {page.get('id', '')}",
            f"url: {page.get('url', '')}",
            "---",
            "",
            f"# {title}",
            "",
            str(page.get("content") or page.get("summary") or ""),
        ])
        return {"success": True, "mode": "plan_only", "target_path": str(target), "content": content}

    @mcp.tool()
    def create_knowledge_sync_checklist(source: str, destination: str, scope: str = "selected notes") -> dict:
        """Create a checklist for a manual Obsidian/Notion sync review."""
        return {
            "success": True,
            "source": source,
            "destination": destination,
            "scope": scope,
            "checklist": [
                "Confirm source of truth for this sync.",
                "Inspect titles, tags, backlinks, and properties before writing.",
                "Convert only selected notes or pages.",
                "Keep original source paths or URLs in metadata.",
                "Review generated payloads before applying them.",
                "Save a memory entry for sync rules that should persist.",
            ],
        }

