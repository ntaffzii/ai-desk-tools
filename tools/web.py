"""Web search and page extraction MCP tools."""

from __future__ import annotations

import json
import re
import urllib.parse
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRUSTED_SOURCES_FILE = PROJECT_ROOT / "trusted_sources.json"


def _load_trusted_sources() -> set[str]:
    try:
        data = json.loads(TRUSTED_SOURCES_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
    sources = data.get("trusted_news_sources", []) + data.get("trusted_domains", [])
    return {str(source).lower() for source in sources}


def _validate_url(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return url


def _absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def _html_to_text(html: str, url: str, max_chars: int = 35_000) -> dict:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {"success": False, "error": "beautifulsoup4_not_installed", "url": url}

    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    description = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})

    root = soup.find("article") or soup.find("main") or soup.find("div", {"role": "main"}) or soup.body or soup
    for element in root(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript", "svg", "button", "input"]):
        element.extract()

    for tag in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = tag.get_text(" ", strip=True)
        if text:
            level = int(tag.name[1])
            tag.replace_with(f"\n\n{'#' * level} {text}\n\n")

    for link in root.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        href = link.get("href", "")
        if text and href and not href.startswith(("javascript:", "#")):
            link.replace_with(f"[{text}]({_absolute_url(url, href)})")

    raw = root.get_text("\n")
    lines = [line.strip() for line in raw.splitlines()]
    clean = "\n".join(line for line in lines if line)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    truncated = len(clean) > max_chars

    return {
        "success": bool(clean),
        "url": url,
        "title": title.get_text(" ", strip=True) if title else "",
        "description": description.get("content", "").strip() if description else "",
        "content": clean[:max_chars],
        "truncated": truncated,
    }


def register(mcp) -> None:
    """Register web tools."""

    @mcp.tool()
    def search_web(query: str, max_results: int = 5) -> dict:
        """Search the web using DuckDuckGo."""
        max_results = min(max(1, max_results), 10)
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return {"success": False, "error": "ddgs_not_installed", "query": query}

        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            return {
                "success": True,
                "query": query,
                "results": [
                    {"title": item.get("title", ""), "url": item.get("href", ""), "snippet": item.get("body", "")}
                    for item in results
                ],
            }
        except Exception as exc:
            return {"success": False, "error": str(exc), "query": query}

    @mcp.tool()
    def search_web_news(query: str, max_results: int = 5, trusted_only: bool = False) -> dict:
        """Search recent news using DuckDuckGo news."""
        max_results = min(max(1, max_results), 10)
        trusted = _load_trusted_sources()
        fetch_count = min(max_results * 3, 25) if trusted_only else max_results
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError:
                return {"success": False, "error": "ddgs_not_installed", "query": query}

        try:
            with DDGS() as ddgs:
                raw_results = list(ddgs.news(query, max_results=fetch_count))
        except Exception as exc:
            return {"success": False, "error": str(exc), "query": query}

        results = []
        for item in raw_results:
            source = str(item.get("source", ""))
            url = str(item.get("url", ""))
            host = urllib.parse.urlparse(url).netloc.lower()
            is_trusted = source.lower() in trusted or host in trusted
            if trusted_only and not is_trusted:
                continue
            results.append(
                {
                    "title": item.get("title", ""),
                    "url": url,
                    "source": source,
                    "date": item.get("date", ""),
                    "snippet": item.get("body", ""),
                    "trusted": is_trusted,
                }
            )
            if len(results) >= max_results:
                break

        return {"success": True, "query": query, "trusted_only": trusted_only, "results": results}

    @mcp.tool()
    def browse_webpage(url: str, timeout_seconds: int = 15, max_chars: int = 35_000) -> dict:
        """Fetch a static webpage and extract readable text."""
        if not _validate_url(url):
            return {"success": False, "error": "invalid_url", "url": url}
        try:
            import requests
        except ImportError:
            return {"success": False, "error": "requests_not_installed", "url": url}

        timeout_seconds = min(max(3, timeout_seconds), 60)
        headers = {"User-Agent": "AI-Desk-Tools/1.0 (+https://github.com)"}
        try:
            response = requests.get(url, headers=headers, timeout=timeout_seconds)
            response.raise_for_status()
            return _html_to_text(response.text, url, max_chars=max_chars)
        except Exception as exc:
            return {"success": False, "error": str(exc), "url": url}

    @mcp.tool()
    async def browse_dynamic_webpage(url: str, wait_selector: str | None = None, timeout_ms: int = 15_000, max_chars: int = 35_000) -> dict:
        """Use Playwright to fetch a JavaScript-rendered webpage."""
        if not _validate_url(url):
            return {"success": False, "error": "invalid_url", "url": url}

        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {"success": False, "error": "playwright_not_installed"}

        timeout_ms = min(max(3_000, timeout_ms), 60_000)
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                page = await browser.new_page(viewport={"width": 1280, "height": 800})
                await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                if wait_selector:
                    await page.wait_for_selector(wait_selector, timeout=timeout_ms)
                else:
                    await page.wait_for_timeout(1500)
                html = await page.content()
                await browser.close()
            return _html_to_text(html, url, max_chars=max_chars)
        except Exception as exc:
            return {"success": False, "error": str(exc), "url": url}

    @mcp.tool()
    def fetch_url(url: str) -> dict:
        """Alias for browse_webpage."""
        return browse_webpage(url)

    @mcp.tool()
    def extract_page_text(html: str, url: str = "https://example.local") -> dict:
        """Extract readable text from provided HTML."""
        return _html_to_text(html, url)

    @mcp.tool()
    def summarize_sources(sources: list[dict]) -> dict:
        """Return a compact source list for agent-side summarization."""
        return {
            "success": True,
            "count": len(sources),
            "sources": [
                {
                    "title": source.get("title", ""),
                    "url": source.get("url", ""),
                    "snippet": str(source.get("snippet") or source.get("content") or "")[:500],
                }
                for source in sources
            ],
        }
