"""Slack and Discord planning/read adapter tools."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request


def _slack_token() -> str:
    return os.getenv("SLACK_BOT_TOKEN") or os.getenv("SLACK_TOKEN") or ""


def _discord_token() -> str:
    return os.getenv("DISCORD_BOT_TOKEN") or ""


def register(mcp) -> None:
    """Register Slack/Discord tools."""

    @mcp.tool()
    def check_chat_integrations() -> dict:
        """Check whether Slack or Discord tokens are configured."""
        return {"success": True, "slack_configured": bool(_slack_token()), "discord_configured": bool(_discord_token()), "env_keys": [key for key in ["SLACK_BOT_TOKEN", "SLACK_TOKEN", "DISCORD_BOT_TOKEN"] if os.getenv(key)]}

    @mcp.tool()
    def search_slack_messages(query: str, count: int = 10) -> dict:
        """Search Slack messages when token is configured."""
        token = _slack_token()
        if not token:
            return {"success": False, "error": "slack_token_missing"}
        params = urllib.parse.urlencode({"query": query, "count": max(1, min(int(count), 20))})
        request = urllib.request.Request(f"https://slack.com/api/search.messages?{params}", headers={"Authorization": f"Bearer {token}"})
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read(2_000_000).decode("utf-8", errors="replace"))
        except Exception as exc:
            return {"success": False, "error": "slack_search_failed", "message": str(exc)}
        return {"success": bool(data.get("ok")), "data": data}

    @mcp.tool()
    def summarize_channel_messages(messages_json: str) -> dict:
        """Summarize supplied Slack/Discord messages without calling an API."""
        try:
            messages = json.loads(messages_json)
            if not isinstance(messages, list):
                return {"success": False, "error": "messages_must_be_list"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_messages_json", "message": str(exc)}
        authors = {}
        for item in messages:
            author = str(item.get("user") or item.get("author") or "unknown")
            authors[author] = authors.get(author, 0) + 1
        text = "\n".join(str(item.get("text") or item.get("content") or "") for item in messages)
        return {"success": True, "message_count": len(messages), "authors": authors, "text_excerpt": text[:4000]}

    @mcp.tool()
    def draft_chat_reply(context: str, tone: str = "concise") -> dict:
        """Draft a chat reply without sending it."""
        return {"success": True, "tone": tone, "draft": f"Thanks. I checked this and here is the concise next step: {context[:500]}"}

    @mcp.tool()
    def extract_action_items(messages_json: str) -> dict:
        """Extract likely action items from supplied messages."""
        try:
            messages = json.loads(messages_json)
            if not isinstance(messages, list):
                return {"success": False, "error": "messages_must_be_list"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_messages_json", "message": str(exc)}
        actions = []
        for item in messages:
            text = str(item.get("text") or item.get("content") or "")
            if any(word in text.lower() for word in ["todo", "action", "please", "fix", "follow up", "next"]):
                actions.append({"source": item.get("id") or item.get("ts"), "text": text[:500]})
        return {"success": True, "count": len(actions), "actions": actions}
