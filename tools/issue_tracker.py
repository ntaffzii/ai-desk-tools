"""Issue tracker planning tools for GitHub, Linear, Jira, and personal tasks."""

from __future__ import annotations

import os
import re


ISSUE_RE = re.compile(r"(?:(?P<provider>github|linear|jira)[:\s-]+)?(?P<key>[A-Z][A-Z0-9]+-\d+|#\d+|[a-f0-9-]{8,})", re.I)


def register(mcp) -> None:
    """Register issue tracker tools."""

    @mcp.tool()
    def check_issue_tracker_config() -> dict:
        """Check configured issue tracker tokens without exposing values."""
        keys = ["GITHUB_TOKEN", "GH_TOKEN", "LINEAR_API_KEY", "JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"]
        return {"success": True, "configured": [key for key in keys if os.getenv(key)], "providers": {"github": bool(os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")), "linear": bool(os.getenv("LINEAR_API_KEY")), "jira": bool(os.getenv("JIRA_BASE_URL") and os.getenv("JIRA_API_TOKEN"))}}

    @mcp.tool()
    def parse_issue_reference(text: str) -> dict:
        """Extract likely issue references from text."""
        matches = []
        for match in ISSUE_RE.finditer(text):
            key = match.group("key")
            provider = (match.group("provider") or "unknown").lower()
            if key.startswith("#"):
                provider = "github" if provider == "unknown" else provider
            elif "-" in key and key.split("-", 1)[0].isalpha():
                provider = "jira" if provider == "unknown" else provider
            matches.append({"provider": provider, "key": key, "span": list(match.span())})
        return {"success": True, "count": len(matches), "matches": matches}

    @mcp.tool()
    def draft_issue_from_context(title: str, context: str, tracker: str = "github", labels_csv: str = "") -> dict:
        """Draft an issue payload without creating it."""
        labels = [label.strip() for label in labels_csv.split(",") if label.strip()]
        body = "\n".join([
            "## Context",
            context[:3000],
            "",
            "## Acceptance Criteria",
            "- [ ] Expected behavior is clear.",
            "- [ ] Implementation is verified.",
            "- [ ] Notes or decisions are saved when useful.",
        ])
        return {"success": True, "tracker": tracker, "payload": {"title": title, "body": body, "labels": labels}}

    @mcp.tool()
    def break_down_issue(title: str, body: str) -> dict:
        """Break an issue into implementation checklist items."""
        tasks = [
            f"Clarify scope for: {title}",
            "Inspect related docs, code, notes, and prior decisions.",
            "Identify smallest shippable behavior.",
            "Implement with narrow validation.",
            "Update docs or notes if behavior changed.",
            "Prepare handoff with tests and remaining risks.",
        ]
        if any(word in body.lower() for word in ["notion", "obsidian", "note"]):
            tasks.insert(2, "Check Notion/Obsidian context before editing.")
        if any(word in body.lower() for word in ["ui", "figma", "frontend"]):
            tasks.insert(2, "Inspect Figma/page map before frontend changes.")
        return {"success": True, "title": title, "tasks": tasks}

    @mcp.tool()
    def plan_issue_update(issue_key: str, summary: str, status: str = "todo") -> dict:
        """Plan an issue update without sending it."""
        return {"success": True, "mode": "plan_only", "issue_key": issue_key, "status": status, "comment": summary[:3000]}

