"""Calendar and meeting-prep planning tools."""

from __future__ import annotations

import json
import os
from datetime import date


def _load_events(events_json: str) -> tuple[list[dict] | None, dict | None]:
    try:
        events = json.loads(events_json)
        if not isinstance(events, list):
            return None, {"success": False, "error": "events_must_be_list"}
        return events, None
    except json.JSONDecodeError as exc:
        return None, {"success": False, "error": "invalid_events_json", "message": str(exc)}


def register(mcp) -> None:
    """Register calendar tools."""

    @mcp.tool()
    def check_calendar_config() -> dict:
        """Check whether calendar provider env keys are configured."""
        keys = ["GOOGLE_CALENDAR_CREDENTIALS", "GOOGLE_CALENDAR_TOKEN", "OUTLOOK_TOKEN", "CALENDAR_ICS_URL"]
        return {"success": True, "configured": [key for key in keys if os.getenv(key)]}

    @mcp.tool()
    def summarize_calendar_events(events_json: str) -> dict:
        """Summarize supplied calendar events."""
        events, error = _load_events(events_json)
        if error:
            return error
        by_day: dict[str, int] = {}
        meetings = []
        for event in events or []:
            day = str(event.get("date") or event.get("start", ""))[:10] or "unknown"
            by_day[day] = by_day.get(day, 0) + 1
            meetings.append({"title": event.get("title") or event.get("summary"), "start": event.get("start"), "attendees": event.get("attendees", [])})
        return {"success": True, "count": len(events or []), "by_day": by_day, "meetings": meetings[:20]}

    @mcp.tool()
    def build_daily_plan(events_json: str, priorities_csv: str = "", day: str | None = None) -> dict:
        """Build a personal daily plan from events and priorities."""
        events, error = _load_events(events_json)
        if error:
            return error
        target_day = day or date.today().isoformat()
        priorities = [item.strip() for item in priorities_csv.split(",") if item.strip()]
        todays = [event for event in events or [] if str(event.get("date") or event.get("start", "")).startswith(target_day)]
        plan = {
            "morning": ["Review calendar", "Pick top 3 priorities"] + priorities[:3],
            "meetings": [{"title": event.get("title") or event.get("summary"), "start": event.get("start")} for event in todays],
            "shutdown": ["Capture decisions", "Move action items to Obsidian/Notion", "Prepare tomorrow"],
        }
        return {"success": True, "day": target_day, "plan": plan}

    @mcp.tool()
    def draft_meeting_prep(event_json: str, context: str = "") -> dict:
        """Draft a meeting-prep note from one event and optional context."""
        try:
            event = json.loads(event_json)
            if not isinstance(event, dict):
                return {"success": False, "error": "event_must_be_object"}
        except json.JSONDecodeError as exc:
            return {"success": False, "error": "invalid_event_json", "message": str(exc)}
        title = event.get("title") or event.get("summary") or "Meeting"
        note = "\n".join([
            f"# {title}",
            "",
            "## Goal",
            "- ",
            "",
            "## Context",
            context[:2000],
            "",
            "## Questions",
            "- What decision is needed?",
            "- What can be delegated or deferred?",
            "",
            "## Follow Ups",
            "- [ ] ",
        ])
        return {"success": True, "title": title, "note": note}

    @mcp.tool()
    def extract_calendar_followups(events_json: str) -> dict:
        """Extract likely follow-up items from supplied event descriptions."""
        events, error = _load_events(events_json)
        if error:
            return error
        followups = []
        for event in events or []:
            text = " ".join([str(event.get("title") or event.get("summary") or ""), str(event.get("description") or "")])
            if any(word in text.lower() for word in ["follow up", "todo", "action", "prepare", "send"]):
                followups.append({"title": event.get("title") or event.get("summary"), "text": text[:500]})
        return {"success": True, "count": len(followups), "followups": followups}

