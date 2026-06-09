"""Provider-neutral web capture and extraction MCP tools.

The default provider is local-first. Optional providers such as Firecrawl can be
enabled with environment variables, but these tools keep the same output shape
so skills and workflows stay portable across agents.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from html import unescape

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


SOCIAL_DOMAINS = {
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "threads.net": "threads",
    "www.threads.net": "threads",
    "x.com": "x",
    "twitter.com": "x",
    "www.tiktok.com": "tiktok",
    "tiktok.com": "tiktok",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
}


def _validate_url(url: str, allow_file: bool = False) -> str:
    parsed = urllib.parse.urlparse(url)
    allowed = {"http", "https"} | ({"file"} if allow_file else set())
    if parsed.scheme not in allowed:
        raise PolicyError("unsupported_url_scheme", "Only http and https URLs are supported", {"url": url})
    if parsed.scheme == "file":
        resolve_allowed_path(parsed.path, access="read")
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise PolicyError("invalid_url", "URL must include a host", {"url": url})
    return url


def _host(url: str) -> str:
    return urllib.parse.urlparse(url).netloc.lower()


def _social_policy(url: str) -> dict:
    host = _host(url)
    platform = SOCIAL_DOMAINS.get(host)
    is_social = bool(platform)
    return {
        "is_social_domain": is_social,
        "platform": platform,
        "public_only": True,
        "auth_bypass_allowed": False,
        "captcha_bypass_allowed": False,
        "official_api_preferred": is_social,
        "notes": [
            "Capture only public content that the current provider can access normally.",
            "Do not bypass login walls, CAPTCHAs, paywalls, private accounts, or platform access controls.",
            "For stable Facebook/Instagram/LinkedIn data, prefer official APIs or user-provided exports when available.",
        ]
        if is_social
        else [],
    }


def _absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def _html_to_markdown(html: str, url: str, max_chars: int = 35_000) -> dict:
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        title_match = re.search(r"<title[^>]*>([\s\S]*?)</title>", html, flags=re.IGNORECASE)
        description_match = re.search(r"<meta[^>]+(?:name|property)=[\"'](?:description|og:description)[\"'][^>]+content=[\"']([^\"']*)[\"']", html, flags=re.IGNORECASE)
        links = []
        for match in re.finditer(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>", html, flags=re.IGNORECASE):
            href = match.group(1)
            text = re.sub(r"<[^>]+>", " ", match.group(2))
            if href and not href.startswith(("javascript:", "#")):
                links.append({"text": re.sub(r"\s+", " ", unescape(text)).strip()[:200], "url": _absolute_url(url, href)})
        text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", html, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", unescape(text)).strip()
        return {
            "success": bool(clean),
            "url": url,
            "title": re.sub(r"\s+", " ", unescape(title_match.group(1))).strip() if title_match else "",
            "description": unescape(description_match.group(1)).strip() if description_match else "",
            "content": clean[:max_chars],
            "truncated": len(clean) > max_chars,
            "links": links[:200],
        }

    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    description = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    root = soup.find("article") or soup.find("main") or soup.find("div", {"role": "main"}) or soup.body or soup

    links = []
    for link in root.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        href = link.get("href", "")
        if href and not href.startswith(("javascript:", "#")):
            absolute = _absolute_url(url, href)
            links.append({"text": text[:200], "url": absolute})
            if text:
                link.replace_with(f"[{text}]({absolute})")

    for element in root(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript", "svg", "button", "input"]):
        element.extract()
    for tag in root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = tag.get_text(" ", strip=True)
        if text:
            tag.replace_with(f"\n\n{'#' * int(tag.name[1])} {text}\n\n")

    raw = root.get_text("\n")
    lines = [line.strip() for line in raw.splitlines()]
    clean = "\n".join(line for line in lines if line)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return {
        "success": bool(clean),
        "url": url,
        "title": title.get_text(" ", strip=True) if title else "",
        "description": description.get("content", "").strip() if description else "",
        "content": clean[:max_chars],
        "truncated": len(clean) > max_chars,
        "links": links[:200],
    }


def _fetch_static(url: str, timeout_seconds: int, max_chars: int) -> dict:
    headers = {"User-Agent": "AI-Desk-Tools/1.0 public-web-capture"}
    try:
        import requests

        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        html = response.text
        status_code = response.status_code
    except ImportError:
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            html = response.read(2_000_000).decode("utf-8", errors="replace")
            status_code = response.getcode()
    extracted = _html_to_markdown(html, url, max_chars=max_chars)
    return {**extracted, "provider": "local-static", "status_code": status_code}


def _fetch_browser(url: str, wait_ms: int, max_chars: int) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"success": False, "error": "playwright_not_installed", "provider": "local-browser"}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(max(0, min(int(wait_ms), 10_000)))
            html = page.content()
            final_url = page.url
            browser.close()
        extracted = _html_to_markdown(html, final_url, max_chars=max_chars)
        return {**extracted, "provider": "local-browser", "final_url": final_url}
    except Exception as exc:
        return {"success": False, "error": "browser_capture_failed", "message": str(exc), "provider": "local-browser", "url": url}


def _fetch_firecrawl(url: str, max_chars: int) -> dict:
    api_key = os.getenv("FIRECRAWL_API_KEY", "")
    api_url = os.getenv("FIRECRAWL_API_URL", "https://api.firecrawl.dev").rstrip("/")
    if not api_key:
        return {"success": False, "error": "firecrawl_token_missing", "provider": "firecrawl", "message": "Set FIRECRAWL_API_KEY to use Firecrawl capture."}
    payload = json.dumps({"url": url, "formats": ["markdown", "html"], "onlyMainContent": True}).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url}/v2/scrape",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read(5_000_000).decode("utf-8", errors="replace"))
    except Exception as exc:
        return {"success": False, "error": "firecrawl_capture_failed", "provider": "firecrawl", "message": str(exc), "url": url}
    page = data.get("data", data)
    content = str(page.get("markdown") or page.get("content") or "")[:max_chars]
    return {
        "success": bool(content),
        "provider": "firecrawl",
        "url": url,
        "title": page.get("metadata", {}).get("title", ""),
        "description": page.get("metadata", {}).get("description", ""),
        "content": content,
        "truncated": len(str(page.get("markdown") or page.get("content") or "")) > max_chars,
        "raw_status": data.get("success"),
    }


def register(mcp) -> None:
    """Register provider-neutral web capture tools."""

    @mcp.tool()
    def list_web_capture_providers() -> dict:
        """List configured web capture providers and capabilities."""
        return {
            "success": True,
            "providers": [
                {"id": "local-static", "configured": True, "capabilities": ["fetch", "html_to_markdown", "links"], "best_for": "Static public pages"},
                {"id": "local-browser", "configured": True, "capabilities": ["javascript_render", "html_to_markdown"], "best_for": "Public JS-rendered pages when Playwright browsers are installed"},
                {"id": "firecrawl", "configured": bool(os.getenv("FIRECRAWL_API_KEY")), "capabilities": ["scrape", "crawl_ready", "structured_ready"], "best_for": "Harder public pages and provider-hosted scraping"},
            ],
        }

    @mcp.tool()
    def plan_web_capture(url: str, target: str = "readable_text") -> dict:
        """Plan provider order and safety limits for a URL capture."""
        try:
            safe_url = _validate_url(url)
        except PolicyError as exc:
            return policy_error_result(exc)
        policy = _social_policy(safe_url)
        provider_order = ["local-static", "local-browser"]
        if os.getenv("FIRECRAWL_API_KEY"):
            provider_order.append("firecrawl")
        return {
            "success": True,
            "url": safe_url,
            "target": target,
            "provider_order": provider_order,
            "social_policy": policy,
            "limits": {"public_only": True, "no_auth_bypass": True, "no_captcha_bypass": True, "max_batch_urls": 10},
        }

    @mcp.tool()
    def extract_html_content(html: str, url: str = "https://example.local", max_chars: int = 35_000) -> dict:
        """Extract readable Markdown-like content and links from provided HTML."""
        result = _html_to_markdown(html, url, max_chars=max_chars)
        audit("web_capture.extract_html_content", result.get("success", False), {"url": url})
        return result

    @mcp.tool()
    def extract_links_from_html(html: str, url: str = "https://example.local", internal_only: bool = False) -> dict:
        """Extract links from provided HTML."""
        result = _html_to_markdown(html, url, max_chars=1)
        base_host = _host(url)
        links = result.get("links", [])
        if internal_only:
            links = [link for link in links if _host(link["url"]) == base_host]
        return {"success": True, "url": url, "internal_only": internal_only, "count": len(links), "links": links}

    @mcp.tool()
    def capture_webpage(url: str, provider: str = "auto", wait_ms: int = 1500, timeout_seconds: int = 15, max_chars: int = 35_000) -> dict:
        """Capture a public webpage through local or optional external providers."""
        try:
            safe_url = _validate_url(url)
        except PolicyError as exc:
            return policy_error_result(exc)

        provider = provider.strip().lower()
        if provider not in {"auto", "local-static", "local-browser", "firecrawl"}:
            return {"success": False, "error": "unknown_provider", "provider": provider}

        if provider in {"auto", "local-static"}:
            try:
                result = _fetch_static(safe_url, timeout_seconds=min(max(3, timeout_seconds), 60), max_chars=max_chars)
                if provider == "local-static" or result.get("content"):
                    audit("web_capture.capture_webpage", result.get("success", False), {"url": safe_url, "provider": result.get("provider")})
                    return {**result, "social_policy": _social_policy(safe_url)}
            except Exception as exc:
                if provider == "local-static":
                    return {"success": False, "error": "static_capture_failed", "message": str(exc), "provider": "local-static", "url": safe_url}

        if provider in {"auto", "local-browser"}:
            result = _fetch_browser(safe_url, wait_ms=wait_ms, max_chars=max_chars)
            if provider == "local-browser" or result.get("success"):
                audit("web_capture.capture_webpage", result.get("success", False), {"url": safe_url, "provider": result.get("provider")})
                return {**result, "social_policy": _social_policy(safe_url)}

        result = _fetch_firecrawl(safe_url, max_chars=max_chars)
        audit("web_capture.capture_webpage", result.get("success", False), {"url": safe_url, "provider": result.get("provider")})
        return {**result, "social_policy": _social_policy(safe_url)}

    @mcp.tool()
    def capture_social_public_url(url: str, provider: str = "auto", wait_ms: int = 1500, max_chars: int = 35_000) -> dict:
        """Capture public social/web content without bypassing login, CAPTCHA, or private access controls."""
        try:
            safe_url = _validate_url(url)
        except PolicyError as exc:
            return policy_error_result(exc)
        policy = _social_policy(safe_url)
        result = capture_webpage(safe_url, provider=provider, wait_ms=wait_ms, max_chars=max_chars)
        return {**result, "social_policy": policy, "recommended_fallback": "Use official API, user export, or user-provided HTML if the platform blocks public access."}

    @mcp.tool()
    def batch_capture_urls(urls_json: str, provider: str = "auto", max_chars_per_page: int = 12_000) -> dict:
        """Capture up to 10 public URLs and return compact content records."""
        try:
            urls = json.loads(urls_json)
            if not isinstance(urls, list):
                return {"success": False, "error": "urls_must_be_list"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_urls_json", "message": str(exc)}
        results = []
        for raw_url in urls[:10]:
            results.append(capture_webpage(str(raw_url), provider=provider, max_chars=max_chars_per_page))
        return {"success": True, "count": len(results), "results": results, "truncated": len(urls) > 10}
