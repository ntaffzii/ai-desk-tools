"""Prompt improvement history storage."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .improver import ImproveResult


@dataclass
class HistoryEntry:
    id: str
    created_at: str
    original_prompt: str
    improved_prompt: str
    task_type: str
    quality_before: int
    quality_after: int
    changes_summary: list[str]
    model_used: str
    tags: list[str]


class PromptHistory:
    """Persist prompt improvement history as JSON."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.path = storage_path or Path("prompt_history.json")
        self._entries: list[HistoryEntry] = []
        self._load()

    def save(self, result: ImproveResult, tags: list[str] | None = None) -> HistoryEntry:
        entry = HistoryEntry(
            id=str(uuid.uuid4())[:8],
            created_at=datetime.now().isoformat(timespec="seconds"),
            original_prompt=result.original_prompt,
            improved_prompt=result.improved_prompt,
            task_type=result.task_type,
            quality_before=result.quality_before,
            quality_after=result.quality_after,
            changes_summary=result.changes_summary,
            model_used=result.model_used,
            tags=tags or [],
        )
        self._entries.append(entry)
        self._save()
        return entry

    def list_all(self) -> list[HistoryEntry]:
        return list(reversed(self._entries))

    def search(self, keyword: str | None = None, task_type: str | None = None, tag: str | None = None) -> list[HistoryEntry]:
        results = self._entries
        if keyword:
            needle = keyword.lower()
            results = [entry for entry in results if needle in entry.original_prompt.lower() or needle in entry.improved_prompt.lower()]
        if task_type:
            results = [entry for entry in results if entry.task_type == task_type]
        if tag:
            results = [entry for entry in results if tag in entry.tags]
        return list(reversed(results))

    def stats(self) -> dict:
        if not self._entries:
            return {"total": 0}
        improvements = [entry.quality_after - entry.quality_before for entry in self._entries]
        by_task: dict[str, int] = {}
        for entry in self._entries:
            by_task[entry.task_type] = by_task.get(entry.task_type, 0) + 1
        return {
            "total": len(self._entries),
            "avg_improvement": round(sum(improvements) / len(improvements), 1),
            "max_improvement": max(improvements),
            "by_task_type": by_task,
            "latest": self._entries[-1].created_at,
        }

    def export_markdown(self, output_path: str = "prompt_history.md") -> str:
        path = Path(output_path)
        lines = ["# Prompt Improve History", "", f"Generated: {datetime.now().isoformat(timespec='seconds')}", ""]
        stats = self.stats()
        lines.extend(["## Summary", "", f"- Total entries: {stats.get('total', 0)}"])
        if stats.get("total", 0):
            lines.extend([f"- Avg improvement: +{stats['avg_improvement']}", f"- Best improvement: +{stats['max_improvement']}"])
        lines.append("")
        for entry in self.list_all():
            improvement = entry.quality_after - entry.quality_before
            lines.extend(
                [
                    "---",
                    f"## {entry.id} - {entry.task_type}",
                    f"- Created: {entry.created_at}",
                    f"- Quality: {entry.quality_before} -> {entry.quality_after} ({improvement:+})",
                    f"- Model: {entry.model_used}",
                    "",
                    "### Original",
                    "```text",
                    entry.original_prompt,
                    "```",
                    "",
                    "### Improved",
                    "```text",
                    entry.improved_prompt,
                    "```",
                    "",
                ]
            )
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path.resolve())

    def _load(self) -> None:
        if not self.path.exists():
            self._entries = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self._entries = [HistoryEntry(**item) for item in raw]
        except Exception:
            self._entries = []

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps([asdict(entry) for entry in self._entries], ensure_ascii=False, indent=2), encoding="utf-8")
