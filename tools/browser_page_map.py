"""Token-efficient browser/page map tools."""

from __future__ import annotations

import re
import urllib.parse
from html import unescape


def _absolute(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", value))).strip()


def _map_html(html: str, url: str) -> dict:
    title_match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, re.I)
    headings = []
    for match in re.finditer(r"<(h[1-6])[^>]*>([\s\S]*?)</\1>", html, re.I):
        headings.append({"level": int(match.group(1)[1]), "text": _strip_tags(match.group(2))[:240]})
    links = []
    for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>", html, re.I):
        text = _strip_tags(match.group(2))
        if text:
            links.append({"text": text[:160], "url": _absolute(url, match.group(1))})
    controls = []
    for pattern, kind in ((r"<button[^>]*>([\s\S]*?)</button>", "button"), (r"<input[^>]*>", "input"), (r"<textarea[^>]*>", "textarea"), (r"<select[^>]*>", "select")):
        for match in re.finditer(pattern, html, re.I):
            raw = match.group(0)
            label = _strip_tags(match.group(1)) if kind == "button" and match.lastindex else ""
            name = re.search(r"(?:name|aria-label|placeholder)=[\"']([^\"']+)[\"']", raw, re.I)
            controls.append({"kind": kind, "label": label or (name.group(1) if name else ""), "raw_excerpt": raw[:300]})
    landmarks = []
    for tag in ["main", "nav", "header", "footer", "form", "article", "aside"]:
        if re.search(fr"<{tag}\b", html, re.I):
            landmarks.append(tag)
    return {
        "success": True,
        "url": url,
        "title": _strip_tags(title_match.group(1)) if title_match else "",
        "headings": headings[:80],
        "links": links[:120],
        "interactive_elements": controls[:120],
        "landmarks": landmarks,
        "counts": {"headings": len(headings), "links": len(links), "interactive_elements": len(controls), "landmarks": len(landmarks)},
    }


def register(mcp) -> None:
    """Register page-map tools."""

    @mcp.tool()
    def capture_page_map_from_html(html: str, url: str = "https://example.local") -> dict:
        """Create a token-efficient page map from provided HTML."""
        return _map_html(html, url)

    @mcp.tool()
    def summarize_page_structure(html: str, url: str = "https://example.local") -> dict:
        """Summarize page structure from HTML."""
        page_map = _map_html(html, url)
        return {"success": True, "url": url, "title": page_map["title"], "counts": page_map["counts"], "top_headings": page_map["headings"][:12], "landmarks": page_map["landmarks"]}

    @mcp.tool()
    def list_interactive_elements(html: str, url: str = "https://example.local") -> dict:
        """List buttons, inputs, selects, textareas, and forms from HTML."""
        page_map = _map_html(html, url)
        return {"success": True, "url": url, "count": len(page_map["interactive_elements"]), "elements": page_map["interactive_elements"]}

    @mcp.tool()
    def find_element_by_label(html: str, label: str, url: str = "https://example.local") -> dict:
        """Find an interactive element by visible label or accessible name."""
        needle = label.lower().strip()
        if not needle:
            return {"success": False, "error": "empty_label"}
        page_map = _map_html(html, url)
        matches = [item for item in page_map["interactive_elements"] if needle in item.get("label", "").lower()]
        return {"success": True, "url": url, "label": label, "count": len(matches), "matches": matches}
