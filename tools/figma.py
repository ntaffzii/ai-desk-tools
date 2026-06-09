"""Figma API planning and read tools."""

from __future__ import annotations

import os
import re
import urllib.request
import json


def _token() -> str:
    return os.getenv("FIGMA_TOKEN") or os.getenv("FIGMA_ACCESS_TOKEN") or ""


def _file_key(value: str) -> str:
    match = re.search(r"/file/([A-Za-z0-9]+)", value)
    return match.group(1) if match else value.strip()


def _get(path: str) -> dict:
    token = _token()
    if not token:
        return {"success": False, "error": "figma_token_missing", "message": "Set FIGMA_TOKEN."}
    request = urllib.request.Request(f"https://api.figma.com/v1{path}", headers={"X-Figma-Token": token})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read(5_000_000).decode("utf-8", errors="replace"))


def register(mcp) -> None:
    """Register Figma tools."""

    @mcp.tool()
    def check_figma_auth() -> dict:
        """Check whether Figma token is configured."""
        return {"success": True, "configured": bool(_token()), "env_keys": [key for key in ["FIGMA_TOKEN", "FIGMA_ACCESS_TOKEN"] if os.getenv(key)]}

    @mcp.tool()
    def plan_figma_inspection(file_url_or_key: str) -> dict:
        """Plan Figma file inspection."""
        key = _file_key(file_url_or_key)
        return {"success": True, "file_key": key, "steps": ["get_figma_file_summary", "extract_design_tokens", "inspect_components", "draft_frontend_implementation_plan"]}

    @mcp.tool()
    def get_figma_file_summary(file_url_or_key: str) -> dict:
        """Fetch Figma file metadata when token is configured."""
        key = _file_key(file_url_or_key)
        try:
            data = _get(f"/files/{key}")
        except Exception as exc:
            return {"success": False, "error": "figma_fetch_failed", "message": str(exc), "file_key": key}
        document = data.get("document", {})
        return {"success": True, "file_key": key, "name": data.get("name"), "last_modified": data.get("lastModified"), "document_name": document.get("name"), "top_level_pages": [child.get("name") for child in document.get("children", [])]}

    @mcp.tool()
    def extract_design_tokens(figma_json: str) -> dict:
        """Extract simple color/style token hints from supplied Figma JSON."""
        try:
            data = json.loads(figma_json)
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_figma_json", "message": str(exc)}
        text = json.dumps(data)
        colors = sorted(set(re.findall(r'"[rgbRGB]"\s*:\s*(0(?:\.\d+)?|1(?:\.0+)?)', text)))[:40]
        return {"success": True, "color_value_count": len(colors), "color_values": colors}

    @mcp.tool()
    def inspect_components(figma_json: str) -> dict:
        """Inspect component-like records from supplied Figma JSON."""
        try:
            data = json.loads(figma_json)
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_figma_json", "message": str(exc)}
        text = json.dumps(data)
        names = sorted(set(re.findall(r'"name"\s*:\s*"([^"]{1,80})"', text)))[:100]
        return {"success": True, "name_count": len(names), "names": names}

    @mcp.tool()
    def draft_frontend_implementation_plan(component_name: str, framework: str = "react") -> dict:
        """Draft a frontend implementation plan from design context."""
        return {"success": True, "component_name": component_name, "framework": framework, "steps": ["Inspect design tokens", "Identify states and variants", "Map layout to existing components", "Implement responsive UI", "Verify with screenshots and accessibility checks"]}
