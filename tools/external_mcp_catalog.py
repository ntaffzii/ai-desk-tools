"""External MCP catalog research tools."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request


CATALOGS = [
    {"name": "modelcontextprotocol/servers", "url": "https://github.com/modelcontextprotocol/servers"},
    {"name": "appcypher/awesome-mcp-servers", "url": "https://github.com/appcypher/awesome-mcp-servers"},
    {"name": "abordage/awesome-mcp", "url": "https://github.com/abordage/awesome-mcp"},
    {"name": "mcp-awesome", "url": "https://mcp-awesome.com/"},
]


def _fetch(url: str, timeout_seconds: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "AI-Desk-Tools/1.0 mcp-catalog"})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return response.read(1_500_000).decode("utf-8", errors="replace")


def _repo_from_url(url: str) -> str:
    match = re.search(r"github\.com/([^/\s]+/[^/\s#?]+)", url)
    return match.group(1).rstrip(".git") if match else ""


def register(mcp) -> None:
    """Register external MCP catalog tools."""

    @mcp.tool()
    def list_mcp_catalog_sources() -> dict:
        """List known MCP catalog sources."""
        return {"success": True, "sources": CATALOGS}

    @mcp.tool()
    def search_mcp_catalogs(query: str, max_results: int = 10) -> dict:
        """Return search URLs for MCP catalogs and GitHub."""
        if not query.strip():
            return {"success": False, "error": "empty_query"}
        safe_limit = max(1, min(int(max_results), 20))
        encoded = urllib.parse.quote_plus(query + " MCP server")
        results = [
            {"title": "GitHub search", "url": f"https://github.com/search?q={encoded}&type=repositories"},
            {"title": "MCP Awesome search", "url": f"https://mcp-awesome.com/?q={urllib.parse.quote_plus(query)}"},
        ]
        for source in CATALOGS:
            results.append({"title": f"Search manually in {source['name']}", "url": source["url"]})
        return {"success": True, "query": query, "count": min(len(results), safe_limit), "results": results[:safe_limit]}

    @mcp.tool()
    def summarize_mcp_repo(repo_url: str, timeout_seconds: int = 20) -> dict:
        """Fetch a public GitHub repo page or README-like URL and summarize likely MCP capabilities."""
        if not repo_url.startswith(("http://", "https://")):
            return {"success": False, "error": "invalid_url"}
        try:
            text = _fetch(repo_url, timeout_seconds)
        except Exception as exc:
            return {"success": False, "error": "fetch_failed", "message": str(exc), "url": repo_url}
        keywords = ["filesystem", "postgres", "slack", "notion", "playwright", "browser", "github", "memory", "rag", "figma", "discord", "finance"]
        found = [word for word in keywords if word in text.lower()]
        tools = sorted(set(re.findall(r"`([a-zA-Z0-9_:-]{3,60})`", text)))[:80]
        return {"success": True, "url": repo_url, "repo": _repo_from_url(repo_url), "keywords": found, "tool_like_names": tools, "text_excerpt": re.sub(r"\s+", " ", text)[:2000]}

    @mcp.tool()
    def compare_mcp_tool_patterns(patterns_json: str) -> dict:
        """Compare MCP tool pattern records supplied as JSON list."""
        try:
            patterns = json.loads(patterns_json)
            if not isinstance(patterns, list):
                return {"success": False, "error": "patterns_must_be_list"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_patterns_json", "message": str(exc)}
        categories = {}
        for item in patterns:
            category = str(item.get("category") or item.get("type") or "unknown")
            categories.setdefault(category, 0)
            categories[category] += 1
        return {"success": True, "count": len(patterns), "categories": categories, "recommendation": "Prefer local, read-only, provider-neutral adapters before mutating SaaS integrations."}

    @mcp.tool()
    def draft_local_tool_adaptation(repo_url: str, desired_capability: str) -> dict:
        """Draft how to adapt an external MCP pattern into this local tools repo."""
        return {
            "success": True,
            "repo_url": repo_url,
            "desired_capability": desired_capability,
            "local_contract": {
                "module": f"mcp-tools/tools/{re.sub(r'[^a-z0-9]+', '_', desired_capability.lower()).strip('_')}.py",
                "default_mode": "read_or_plan_first",
                "auth": "environment variables only",
                "tests": "offline tests for validation and parsing; live-provider tests optional",
                "docs": ["README.md", "docs/TOOLS_INVENTORY.md", "data/tools.json", "data/toolsets.json"],
            },
        }
