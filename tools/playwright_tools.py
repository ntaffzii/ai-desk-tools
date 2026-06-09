"""Playwright MCP tools for local page inspection."""

from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


def _playwright():
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - depends on optional install
        return None, None, exc
    return sync_playwright, PlaywrightError, None


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "file"}:
        raise PolicyError("unsupported_url_scheme", "Only http, https, and file URLs are supported", {"url": url})
    if parsed.scheme == "file":
        resolve_allowed_path(parsed.path, access="read")
    return url


def _output_path(output_path: str | None) -> Path:
    target = output_path or "C:/tmp/playwright-screenshot.png"
    path = resolve_allowed_path(target, access="write")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def register(mcp) -> None:
    """Register Playwright tools."""

    @mcp.tool()
    def check_playwright_runtime() -> dict:
        """Check whether Python Playwright is importable."""
        sync_playwright, _, exc = _playwright()
        return {"success": exc is None, "available": sync_playwright is not None, "error": str(exc) if exc else ""}

    @mcp.tool()
    def playwright_inspect_page(url: str, wait_ms: int = 500, text_limit: int = 4000) -> dict:
        """Open a page and return title, final URL, text excerpt, and console errors."""
        try:
            safe_url = _safe_url(url)
        except PolicyError as exc:
            return policy_error_result(exc)

        sync_playwright, PlaywrightError, exc = _playwright()
        if exc:
            return {"success": False, "error": "playwright_unavailable", "message": str(exc)}

        console_errors: list[str] = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.goto(safe_url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(max(0, min(int(wait_ms), 10_000)))
                title = page.title()
                final_url = page.url
                text = page.locator("body").inner_text(timeout=5_000) if page.locator("body").count() else ""
                browser.close()
        except PlaywrightError as err:
            audit("playwright.inspect_page", False, {"url": safe_url, "error": str(err)})
            return {"success": False, "error": "playwright_error", "message": str(err)}

        audit("playwright.inspect_page", True, {"url": safe_url})
        return {"success": True, "url": safe_url, "final_url": final_url, "title": title, "text": text[:text_limit], "console_errors": console_errors}

    @mcp.tool()
    def playwright_screenshot(url: str, output_path: str | None = None, full_page: bool = True, wait_ms: int = 500) -> dict:
        """Capture a screenshot for a page."""
        try:
            safe_url = _safe_url(url)
            path = _output_path(output_path)
        except PolicyError as exc:
            return policy_error_result(exc)

        sync_playwright, PlaywrightError, exc = _playwright()
        if exc:
            return {"success": False, "error": "playwright_unavailable", "message": str(exc)}

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(safe_url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(max(0, min(int(wait_ms), 10_000)))
                page.screenshot(path=str(path), full_page=full_page)
                browser.close()
        except PlaywrightError as err:
            audit("playwright.screenshot", False, {"url": safe_url, "error": str(err)})
            return {"success": False, "error": "playwright_error", "message": str(err)}

        audit("playwright.screenshot", True, {"url": safe_url, "output_path": str(path)})
        return {"success": True, "url": safe_url, "output_path": str(path), "size_bytes": path.stat().st_size}

    @mcp.tool()
    def playwright_smoke_plan(url: str) -> dict:
        """Return a recommended page smoke test plan."""
        return {
            "success": True,
            "url": url,
            "steps": [
                "Open page with domcontentloaded wait",
                "Capture title and final URL",
                "Collect console errors",
                "Capture screenshot",
                "Check visible text for expected labels",
                "Report network/browser runtime errors",
            ],
        }
