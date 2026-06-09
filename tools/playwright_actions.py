"""Playwright browser action MCP tools."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

from security import PolicyError, audit, policy_error_result, resolve_allowed_path


def _playwright():
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover
        return None, None, exc
    return sync_playwright, PlaywrightError, None


_SESSION_MANAGER = None
_SESSION_PLAYWRIGHT = None
_SESSIONS: dict[str, dict] = {}


def _safe_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "file"}:
        raise PolicyError("unsupported_url_scheme", "Only http, https, and file URLs are supported", {"url": url})
    if parsed.scheme == "file":
        resolve_allowed_path(parsed.path, access="read")
    return url


def _safe_output(path: str | None) -> Path | None:
    if not path:
        return None
    target = resolve_allowed_path(path, access="write")
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _run_page(url: str, callback, wait_ms: int = 500):
    try:
        safe_url = _safe_url(url)
    except PolicyError as exc:
        return policy_error_result(exc)
    sync_playwright, PlaywrightError, exc = _playwright()
    if exc:
        return {"success": False, "error": "playwright_unavailable", "message": str(exc)}

    console_errors: list[str] = []
    network_failures: list[dict] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: network_failures.append({"url": req.url, "failure": str(req.failure)}))
            page.goto(safe_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(max(0, min(int(wait_ms), 10_000)))
            result = callback(page)
            title = page.title()
            final_url = page.url
            browser.close()
    except PlaywrightError as err:
        return {"success": False, "error": "playwright_error", "message": str(err)}

    return {"success": True, "url": safe_url, "final_url": final_url, "title": title, "console_errors": console_errors, "network_failures": network_failures, **(result or {})}


def _run_action_sequence(page, actions: list[dict]) -> list[dict]:
    results = []
    for item in actions:
        action = item.get("action")
        if action == "fill":
            page.locator(item["selector"]).fill(str(item.get("value", "")), timeout=10_000)
            results.append({"action": "fill", "selector": item["selector"], "success": True})
        elif action == "click":
            page.locator(item["selector"]).click(timeout=10_000)
            results.append({"action": "click", "selector": item["selector"], "success": True})
        elif action == "assert_text":
            body = page.locator("body").inner_text(timeout=5_000) if page.locator("body").count() else ""
            found = str(item.get("text", "")) in body
            results.append({"action": "assert_text", "text": item.get("text", ""), "success": found})
        elif action == "goto":
            safe_url = _safe_url(str(item["url"]))
            page.goto(safe_url, wait_until="domcontentloaded", timeout=30_000)
            results.append({"action": "goto", "url": safe_url, "success": True})
        else:
            results.append({"action": action, "success": False, "error": "unknown_action"})
    return results


def _ensure_session_manager():
    global _SESSION_MANAGER, _SESSION_PLAYWRIGHT
    if _SESSION_PLAYWRIGHT is not None:
        return None
    sync_playwright, PlaywrightError, exc = _playwright()
    if exc:
        return {"success": False, "error": "playwright_unavailable", "message": str(exc)}
    _SESSION_MANAGER = sync_playwright()
    _SESSION_PLAYWRIGHT = _SESSION_MANAGER.start()
    return None


def _close_session(session_id: str) -> dict:
    session = _SESSIONS.pop(session_id, None)
    if not session:
        return {"success": False, "error": "session_not_found", "session_id": session_id}
    try:
        session["context"].close()
        session["browser"].close()
    except Exception as exc:  # pragma: no cover - browser cleanup detail
        return {"success": False, "error": "session_close_failed", "message": str(exc), "session_id": session_id}
    return {"success": True, "session_id": session_id}


def register(mcp) -> None:
    """Register Playwright action tools."""

    @mcp.tool()
    def playwright_click(url: str, selector: str, wait_ms: int = 500) -> dict:
        """Open a page and click one selector."""
        def action(page):
            page.locator(selector).click(timeout=10_000)
            return {"action": "click", "selector": selector}

        result = _run_page(url, action, wait_ms)
        audit("playwright_actions.click", result.get("success", False), {"url": url, "selector": selector, "error": result.get("error")})
        return result

    @mcp.tool()
    def playwright_fill(url: str, selector: str, value: str, wait_ms: int = 500) -> dict:
        """Open a page and fill one selector."""
        def action(page):
            page.locator(selector).fill(value, timeout=10_000)
            return {"action": "fill", "selector": selector, "value_length": len(value)}

        result = _run_page(url, action, wait_ms)
        audit("playwright_actions.fill", result.get("success", False), {"url": url, "selector": selector, "error": result.get("error")})
        return result

    @mcp.tool()
    def playwright_assert_visible_text(url: str, text: str, wait_ms: int = 500) -> dict:
        """Open a page and assert visible body text contains text."""
        def action(page):
            body = page.locator("body").inner_text(timeout=5_000) if page.locator("body").count() else ""
            return {"expected_text": text, "found": text in body, "body_excerpt": body[:4000]}

        result = _run_page(url, action, wait_ms)
        result["success"] = bool(result.get("success") and result.get("found"))
        audit("playwright_actions.assert_visible_text", result.get("success", False), {"url": url, "text": text, "error": result.get("error")})
        return result

    @mcp.tool()
    def playwright_get_console_errors(url: str, wait_ms: int = 1000) -> dict:
        """Open a page and return console errors."""
        return _run_page(url, lambda page: {"action": "get_console_errors"}, wait_ms)

    @mcp.tool()
    def playwright_get_network_failures(url: str, wait_ms: int = 1000) -> dict:
        """Open a page and return failed network requests."""
        return _run_page(url, lambda page: {"action": "get_network_failures"}, wait_ms)

    @mcp.tool()
    def playwright_accessibility_snapshot(url: str, wait_ms: int = 500, interesting_only: bool = True) -> dict:
        """Open a page and return an accessibility snapshot when Playwright supports it."""
        def action(page):
            snapshot = page.accessibility.snapshot(interesting_only=interesting_only)
            return {"action": "accessibility_snapshot", "snapshot": snapshot}

        result = _run_page(url, action, wait_ms)
        audit("playwright_actions.accessibility_snapshot", result.get("success", False), {"url": url, "error": result.get("error")})
        return result

    @mcp.tool()
    def playwright_run_ui_check(url: str, actions_json: str = "[]", screenshot_path: str | None = None, wait_ms: int = 500) -> dict:
        """Run a small JSON action sequence and optionally capture a screenshot.

        actions_json format:
        [{"action":"fill","selector":"#q","value":"hello"},{"action":"click","selector":"button"},{"action":"assert_text","text":"Done"}]
        """
        try:
            actions = json.loads(actions_json)
            if not isinstance(actions, list):
                return {"success": False, "error": "actions_must_be_list"}
            output = _safe_output(screenshot_path)
        except PolicyError as exc:
            return policy_error_result(exc)
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_actions_json", "message": str(exc)}

        def run_actions(page):
            results = _run_action_sequence(page, actions)
            if output:
                page.screenshot(path=str(output), full_page=True)
            return {"action_results": results, "screenshot_path": str(output) if output else None}

        result = _run_page(url, run_actions, wait_ms)
        if result.get("success"):
            result["success"] = all(item.get("success") for item in result.get("action_results", []))
        audit("playwright_actions.run_ui_check", result.get("success", False), {"url": url, "error": result.get("error")})
        return result

    @mcp.tool()
    def playwright_start_session(url: str, session_id: str | None = None, wait_ms: int = 500) -> dict:
        """Start a persistent browser session and open the initial URL."""
        try:
            safe_url = _safe_url(url)
        except PolicyError as exc:
            return policy_error_result(exc)

        manager_error = _ensure_session_manager()
        if manager_error:
            return manager_error

        safe_session_id = session_id or f"pw-{uuid.uuid4().hex[:10]}"
        if safe_session_id in _SESSIONS:
            return {"success": False, "error": "session_already_exists", "session_id": safe_session_id}

        console_errors: list[str] = []
        network_failures: list[dict] = []
        browser = None
        context = None
        try:
            browser = _SESSION_PLAYWRIGHT.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("requestfailed", lambda req: network_failures.append({"url": req.url, "failure": str(req.failure)}))
            page.goto(safe_url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(max(0, min(int(wait_ms), 10_000)))
        except Exception as exc:
            try:
                if context:
                    context.close()
                if browser:
                    browser.close()
            except Exception:
                pass
            return {"success": False, "error": "playwright_error", "message": str(exc)}

        _SESSIONS[safe_session_id] = {
            "browser": browser,
            "context": context,
            "page": page,
            "url": safe_url,
            "created_at": time.time(),
            "last_used_at": time.time(),
            "console_errors": console_errors,
            "network_failures": network_failures,
        }
        result = {"success": True, "session_id": safe_session_id, "url": safe_url, "final_url": page.url, "title": page.title()}
        audit("playwright_actions.start_session", True, {"url": safe_url, "session_id": safe_session_id})
        return result

    @mcp.tool()
    def playwright_use_session(session_id: str, actions_json: str = "[]", screenshot_path: str | None = None, wait_ms: int = 500) -> dict:
        """Run actions against an existing persistent browser session."""
        session = _SESSIONS.get(session_id)
        if not session:
            return {"success": False, "error": "session_not_found", "session_id": session_id}
        try:
            actions = json.loads(actions_json)
            if not isinstance(actions, list):
                return {"success": False, "error": "actions_must_be_list"}
            output = _safe_output(screenshot_path)
            page = session["page"]
            results = _run_action_sequence(page, actions)
            page.wait_for_timeout(max(0, min(int(wait_ms), 10_000)))
            if output:
                page.screenshot(path=str(output), full_page=True)
            session["last_used_at"] = time.time()
        except PolicyError as exc:
            return policy_error_result(exc)
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_actions_json", "message": str(exc)}
        except Exception as exc:
            audit("playwright_actions.use_session", False, {"session_id": session_id, "error": str(exc)})
            return {"success": False, "error": "playwright_error", "message": str(exc), "session_id": session_id}

        result = {
            "success": all(item.get("success") for item in results),
            "session_id": session_id,
            "final_url": page.url,
            "title": page.title(),
            "action_results": results,
            "screenshot_path": str(output) if output else None,
            "console_errors": session["console_errors"],
            "network_failures": session["network_failures"],
        }
        audit("playwright_actions.use_session", result["success"], {"session_id": session_id, "error": None if result["success"] else "action_failed"})
        return result

    @mcp.tool()
    def playwright_list_sessions() -> dict:
        """List currently open persistent Playwright sessions."""
        sessions = []
        for session_id, session in _SESSIONS.items():
            page = session["page"]
            sessions.append(
                {
                    "session_id": session_id,
                    "url": page.url,
                    "title": page.title(),
                    "created_at": session["created_at"],
                    "last_used_at": session["last_used_at"],
                    "console_error_count": len(session["console_errors"]),
                    "network_failure_count": len(session["network_failures"]),
                }
            )
        return {"success": True, "count": len(sessions), "sessions": sessions}

    @mcp.tool()
    def playwright_close_session(session_id: str) -> dict:
        """Close one persistent Playwright session."""
        result = _close_session(session_id)
        audit("playwright_actions.close_session", result.get("success", False), {"session_id": session_id, "error": result.get("error")})
        return result
