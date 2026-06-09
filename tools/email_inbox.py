"""Email inbox summarization and reply-drafting tools."""

from __future__ import annotations

import json
import os


def _load_messages(messages_json: str) -> tuple[list[dict] | None, dict | None]:
    try:
        messages = json.loads(messages_json)
        if not isinstance(messages, list):
            return None, {"success": False, "error": "messages_must_be_list"}
        return messages, None
    except json.JSONDecodeError as exc:
        return None, {"success": False, "error": "invalid_messages_json", "message": str(exc)}


def register(mcp) -> None:
    """Register email inbox tools."""

    @mcp.tool()
    def check_email_config() -> dict:
        """Check email provider env keys without exposing values."""
        keys = ["GMAIL_CREDENTIALS", "GMAIL_TOKEN", "OUTLOOK_TOKEN", "IMAP_HOST", "IMAP_USERNAME", "IMAP_PASSWORD"]
        return {"success": True, "configured": [key for key in keys if os.getenv(key)]}

    @mcp.tool()
    def plan_email_search(query: str, provider: str = "gmail", limit: int = 10) -> dict:
        """Plan an email search without calling a provider."""
        return {"success": True, "mode": "plan_only", "provider": provider, "query": query, "limit": max(1, min(int(limit), 50)), "privacy_note": "Search only mailboxes the user explicitly configures."}

    @mcp.tool()
    def summarize_email_messages(messages_json: str) -> dict:
        """Summarize supplied email messages."""
        messages, error = _load_messages(messages_json)
        if error:
            return error
        senders: dict[str, int] = {}
        subjects = []
        for item in messages or []:
            sender = str(item.get("from") or item.get("sender") or "unknown")
            senders[sender] = senders.get(sender, 0) + 1
            subjects.append(str(item.get("subject") or "")[:160])
        return {"success": True, "count": len(messages or []), "senders": senders, "subjects": subjects[:20]}

    @mcp.tool()
    def extract_email_action_items(messages_json: str) -> dict:
        """Extract likely email action items from supplied messages."""
        messages, error = _load_messages(messages_json)
        if error:
            return error
        actions = []
        for item in messages or []:
            text = " ".join([str(item.get("subject") or ""), str(item.get("body") or item.get("text") or "")])
            if any(word in text.lower() for word in ["please", "action", "todo", "deadline", "by ", "follow up", "can you"]):
                actions.append({"from": item.get("from") or item.get("sender"), "subject": item.get("subject"), "text": text[:500]})
        return {"success": True, "count": len(actions), "actions": actions}

    @mcp.tool()
    def draft_email_reply(subject: str, context: str, tone: str = "clear and concise") -> dict:
        """Draft an email reply without sending it."""
        body = "\n".join([
            "Hi,",
            "",
            f"Thanks for the note. {context[:1200]}",
            "",
            "Best,",
        ])
        return {"success": True, "mode": "draft_only", "subject": f"Re: {subject}", "tone": tone, "body": body}

