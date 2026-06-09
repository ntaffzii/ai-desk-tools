"""
tools/prompt_improver.py
------------------------
MCP tool สำหรับ improve prompt
ใช้ FastMCP pattern เดียวกับ tools อื่นๆ
"""

from mcp.server.fastmcp import FastMCP

from prompt_engine import PromptAnalyzer, PromptImprover, TemplateSelector, PromptHistory
from prompt_engine.improver import ImproveResult


# -----------------------------------------------------------------------
# Singletons
# -----------------------------------------------------------------------

_analyzer = PromptAnalyzer()
_improver = PromptImprover()
_selector = TemplateSelector()
_history = PromptHistory()


# -----------------------------------------------------------------------
# Register Function
# -----------------------------------------------------------------------

def register(mcp: FastMCP):
    """ลงทะเบียน prompt improver tools เข้า MCP server"""

    @mcp.tool()
    async def improve_prompt(
        prompt: str,
        task_type: str = "",
        save_history: bool = True,
        tags: list[str] = [],
    ) -> dict:
        """
        ปรับปรุง prompt ให้ชัดเจนและมีประสิทธิภาพมากขึ้น
        รองรับภาษาไทยและอังกฤษ ตรวจจับประเภทงานอัตโนมัติ

        Args:
            prompt: prompt ที่ต้องการ improve
            task_type: ประเภทงาน (ถ้าไม่ระบุจะตรวจจับอัตโนมัติ)
                       เลือกได้: rag, code, summary, extraction,
                                translation, analysis, creative, qa, general
            save_history: บันทึกลง history (default: True)
            tags: tags สำหรับจัดกลุ่ม เช่น ["production", "rag"]
        """
        if not prompt.strip():
            return {"error": "prompt is required"}

        # 1. วิเคราะห์
        analysis = _analyzer.analyze(prompt)

        # override task_type ถ้าผู้ใช้ระบุมา
        if task_type and task_type in _selector.list_task_types():
            analysis.task_type = task_type

        # 2. Improve
        result: ImproveResult = await _improver.improve(prompt, analysis)

        # 3. บันทึก history
        history_id = None
        if save_history:
            entry = _history.save(result, tags=tags)
            history_id = entry.id

        return {
            "success": result.success,
            "history_id": history_id,
            "original_prompt": result.original_prompt,
            "improved_prompt": result.improved_prompt,
            "analysis": {
                "language": analysis.language,
                "task_type": result.task_type,
                "quality_before": result.quality_before,
                "quality_after": result.quality_after,
                "improvement": result.quality_after - result.quality_before,
                "issues_found": analysis.issues,
                "changes_made": result.changes_summary,
            },
            "structure_hint": result.structure_hint,
            "error": result.error,
        }

    @mcp.tool()
    def analyze_prompt(prompt: str) -> dict:
        """
        วิเคราะห์ prompt เพื่อหาจุดอ่อนและให้คำแนะนำ
        โดยไม่ทำการปรับปรุง

        Args:
            prompt: prompt ที่ต้องการวิเคราะห์
        """
        if not prompt.strip():
            return {"error": "prompt is required"}

        analysis = _analyzer.analyze(prompt)

        return {
            "language": analysis.language,
            "task_type": analysis.task_type,
            "quality_score": analysis.quality_score,
            "word_count": analysis.word_count,
            "has_context": analysis.has_context,
            "has_examples": analysis.has_examples,
            "has_output_format": analysis.has_output_format,
            "has_constraints": analysis.has_constraints,
            "issues": analysis.issues,
            "suggestions": analysis.suggestions,
            "structure_hint": _selector.get_structure_hint(analysis.task_type),
        }

    @mcp.tool()
    def get_prompt_history(
        limit: int = 10,
        task_type: str = "",
        keyword: str = "",
        tag: str = "",
    ) -> dict:
        """
        ดึงประวัติ prompt ที่ผ่านการ improve

        Args:
            limit: จำนวน entries ที่ต้องการ (default: 10)
            task_type: filter ตามประเภทงาน
            keyword: ค้นหาจากข้อความใน prompt
            tag: filter ตาม tag
        """
        entries = _history.search(
            keyword=keyword or None,
            task_type=task_type or None,
            tag=tag or None,
        )
        entries = entries[:limit]

        return {
            "total_found": len(entries),
            "stats": _history.stats(),
            "entries": [
                {
                    "id": e.id,
                    "created_at": e.created_at,
                    "task_type": e.task_type,
                    "quality_before": e.quality_before,
                    "quality_after": e.quality_after,
                    "improvement": e.quality_after - e.quality_before,
                    "original_preview": (
                        e.original_prompt[:80] + "..."
                        if len(e.original_prompt) > 80
                        else e.original_prompt
                    ),
                    "tags": e.tags,
                }
                for e in entries
            ],
        }

    @mcp.tool()
    def export_prompt_history(output_path: str = "prompt_history.md") -> dict:
        """
        Export ประวัติ prompt ทั้งหมดเป็นไฟล์ Markdown

        Args:
            output_path: path ไฟล์ที่ต้องการ export
        """
        saved_path = _history.export_markdown(output_path)
        stats = _history.stats()

        return {
            "success": True,
            "output_path": saved_path,
            "total_entries": stats.get("total", 0),
        }