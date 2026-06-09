"""Prompt improvement MCP tools."""

from __future__ import annotations

from prompt_engine import PromptAnalyzer, PromptHistory, PromptImprover, TemplateSelector


_analyzer = PromptAnalyzer()
_improver = PromptImprover()
_selector = TemplateSelector()
_history = PromptHistory()


def register(mcp) -> None:
    """Register prompt tools."""

    @mcp.tool()
    def analyze_prompt(prompt: str) -> dict:
        """Analyze prompt quality and return issues, suggestions, and structure hints."""
        analysis = _analyzer.analyze(prompt)
        return {
            "success": bool(prompt.strip()),
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
    async def improve_prompt(prompt: str, task_type: str = "", save_history: bool = True, tags: list[str] | None = None) -> dict:
        """Improve a prompt using the local model endpoint when configured, otherwise rule-based fallback."""
        if not prompt.strip():
            return {"success": False, "error": "prompt is required"}

        analysis = _analyzer.analyze(prompt)
        if task_type and task_type in _selector.list_task_types():
            analysis.task_type = task_type

        result = await _improver.improve(prompt, analysis)
        history_id = None
        if save_history:
            history_id = _history.save(result, tags=tags or []).id

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
                "model_used": result.model_used,
            },
            "structure_hint": result.structure_hint,
            "error": result.error,
        }

    @mcp.tool()
    def generate_system_prompt(task: str, task_type: str = "general") -> dict:
        """Generate a compact system prompt draft for a task."""
        template = _selector.get(task_type)
        return {
            "success": True,
            "task_type": template.task_type,
            "system_prompt": f"{template.system_prompt}\n\nTask: {task}\n\nBe specific, verify important claims, and report remaining risk.",
            "structure_hint": template.structure_hint,
        }

    @mcp.tool()
    def score_prompt(prompt: str) -> dict:
        """Return prompt quality score only."""
        analysis = _analyzer.analyze(prompt)
        return {"success": bool(prompt.strip()), "score": analysis.quality_score, "max_score": 100, "issues": analysis.issues}

    @mcp.tool()
    def get_prompt_history(limit: int = 10, task_type: str = "", keyword: str = "", tag: str = "") -> dict:
        """Return prompt improvement history."""
        limit = min(max(1, limit), 100)
        entries = _history.search(keyword=keyword or None, task_type=task_type or None, tag=tag or None)[:limit]
        return {
            "success": True,
            "total_found": len(entries),
            "stats": _history.stats(),
            "entries": [
                {
                    "id": entry.id,
                    "created_at": entry.created_at,
                    "task_type": entry.task_type,
                    "quality_before": entry.quality_before,
                    "quality_after": entry.quality_after,
                    "improvement": entry.quality_after - entry.quality_before,
                    "original_preview": entry.original_prompt[:120],
                    "tags": entry.tags,
                }
                for entry in entries
            ],
        }

    @mcp.tool()
    def export_prompt_history(output_path: str = "prompt_history.md") -> dict:
        """Export prompt improvement history to Markdown."""
        return {"success": True, "output_path": _history.export_markdown(output_path), "stats": _history.stats()}
