"""
history.py
----------
บันทึกและจัดการประวัติ prompt ที่ผ่านการ improve
เก็บเป็น JSON file บน disk
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

from .improver import ImproveResult


# -----------------------------------------------------------------------
# Data class
# -----------------------------------------------------------------------

@dataclass
class HistoryEntry:
    """1 record ใน history"""
    id: str
    created_at: str                 # ISO format
    original_prompt: str
    improved_prompt: str
    task_type: str
    quality_before: int
    quality_after: int
    changes_summary: list[str]
    model_used: str
    tags: list[str]                 # tags ที่ user กำหนดเอง เช่น ["rag", "production"]


# -----------------------------------------------------------------------
# PromptHistory
# -----------------------------------------------------------------------

class PromptHistory:
    """
    บันทึก / ดึง / ค้นหา history ของ prompt

    ตัวอย่างการใช้งาน:
        history = PromptHistory()
        entry = history.save(improve_result)
        all_entries = history.list_all()
        history.export_markdown("history_report.md")
    """

    DEFAULT_PATH = Path("prompt_history.json")

    def __init__(self, storage_path: Optional[Path] = None):
        self.path = storage_path or self.DEFAULT_PATH
        self._entries: list[HistoryEntry] = []
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(
        self,
        result: ImproveResult,
        tags: Optional[list[str]] = None,
    ) -> HistoryEntry:
        """บันทึก ImproveResult ลง history และ return HistoryEntry"""
        entry = HistoryEntry(
            id=str(uuid.uuid4())[:8],
            created_at=datetime.now().isoformat(),
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
        """คืน entries ทั้งหมด เรียงจากใหม่ไปเก่า"""
        return list(reversed(self._entries))

    def get_by_id(self, entry_id: str) -> Optional[HistoryEntry]:
        """ค้นหา entry จาก id"""
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None

    def search(
        self,
        keyword: Optional[str] = None,
        task_type: Optional[str] = None,
        tag: Optional[str] = None,
        min_improvement: Optional[int] = None,  # quality_after - quality_before
    ) -> list[HistoryEntry]:
        """ค้นหา entries ตามเงื่อนไข"""
        results = self._entries

        if keyword:
            kw = keyword.lower()
            results = [
                e for e in results
                if kw in e.original_prompt.lower()
                or kw in e.improved_prompt.lower()
            ]

        if task_type:
            results = [e for e in results if e.task_type == task_type]

        if tag:
            results = [e for e in results if tag in e.tags]

        if min_improvement is not None:
            results = [
                e for e in results
                if (e.quality_after - e.quality_before) >= min_improvement
            ]

        return list(reversed(results))

    def delete(self, entry_id: str) -> bool:
        """ลบ entry ตาม id คืน True ถ้าสำเร็จ"""
        before = len(self._entries)
        self._entries = [e for e in self._entries if e.id != entry_id]
        if len(self._entries) < before:
            self._save()
            return True
        return False

    def stats(self) -> dict:
        """สถิติรวมของ history"""
        if not self._entries:
            return {"total": 0}

        improvements = [e.quality_after - e.quality_before for e in self._entries]
        by_task: dict[str, int] = {}
        for e in self._entries:
            by_task[e.task_type] = by_task.get(e.task_type, 0) + 1

        return {
            "total": len(self._entries),
            "avg_improvement": round(sum(improvements) / len(improvements), 1),
            "max_improvement": max(improvements),
            "by_task_type": by_task,
            "latest": self._entries[-1].created_at if self._entries else None,
        }

    def export_markdown(self, output_path: str = "prompt_history.md") -> str:
        """export history เป็น Markdown report"""
        lines = ["# Prompt Improve History\n"]
        lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        stats = self.stats()
        lines.append("## Summary\n")
        lines.append(f"- Total entries: {stats['total']}")
        if stats['total'] > 0:
            lines.append(f"- Avg improvement: +{stats['avg_improvement']} points")
            lines.append(f"- Best improvement: +{stats['max_improvement']} points")
        lines.append("")

        for entry in self.list_all():
            improvement = entry.quality_after - entry.quality_before
            sign = "+" if improvement >= 0 else ""
            lines.append(f"---\n")
            lines.append(f"### [{entry.id}] {entry.task_type.upper()} — {entry.created_at[:10]}")
            lines.append(f"**Quality:** {entry.quality_before} → {entry.quality_after} ({sign}{improvement})")
            if entry.tags:
                lines.append(f"**Tags:** {', '.join(entry.tags)}")
            lines.append(f"\n**Original:**\n```\n{entry.original_prompt}\n```")
            lines.append(f"\n**Improved:**\n```\n{entry.improved_prompt}\n```")
            if entry.changes_summary:
                lines.append("\n**Changes:** " + " | ".join(entry.changes_summary))
            lines.append("")

        content = "\n".join(lines)
        Path(output_path).write_text(content, encoding="utf-8")
        return output_path

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """โหลด entries จาก JSON file"""
        if not self.path.exists():
            self._entries = []
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._entries = [HistoryEntry(**e) for e in data]
        except Exception:
            self._entries = []

    def _save(self) -> None:
        """บันทึก entries ลง JSON file"""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self._entries]
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )