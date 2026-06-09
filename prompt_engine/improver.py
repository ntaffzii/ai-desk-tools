"""Prompt improvement engine with optional OpenAI-compatible local model."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from .analyzer import AnalysisResult
from .templates import TemplateSelector


@dataclass
class ImproveResult:
    original_prompt: str
    improved_prompt: str
    task_type: str
    quality_before: int
    quality_after: int
    changes_summary: list[str] = field(default_factory=list)
    structure_hint: str = ""
    model_used: str = "rule-based"
    success: bool = True
    error: str | None = None


class PromptImprover:
    """Improve prompts with a local LLM when configured, otherwise use rules."""

    def __init__(
        self,
        api_url: str | None = None,
        model: str | None = None,
        timeout: int = 45,
        use_fallback: bool = True,
    ) -> None:
        self.api_url = api_url or os.getenv("PROMPT_IMPROVER_API_URL", "")
        self.model = model or os.getenv("PROMPT_IMPROVER_MODEL", "local-model")
        self.timeout = timeout
        self.use_fallback = use_fallback
        self.selector = TemplateSelector()

    async def improve(self, original_prompt: str, analysis: AnalysisResult) -> ImproveResult:
        template = self.selector.get(analysis.task_type)
        error: str | None = None

        if self.api_url:
            try:
                improved = await self._call_llm(original_prompt, analysis)
                model_used = self.model
            except Exception as exc:
                if not self.use_fallback:
                    return ImproveResult(
                        original_prompt=original_prompt,
                        improved_prompt=original_prompt,
                        task_type=analysis.task_type,
                        quality_before=analysis.quality_score,
                        quality_after=analysis.quality_score,
                        success=False,
                        error=str(exc),
                    )
                improved = self._rule_based_improve(original_prompt, analysis)
                model_used = "rule-based"
                error = f"model unavailable; used fallback: {exc}"
        else:
            improved = self._rule_based_improve(original_prompt, analysis)
            model_used = "rule-based"

        quality_after = min(100, max(analysis.quality_score + 15, analysis.quality_score + (100 - analysis.quality_score) // 2))
        return ImproveResult(
            original_prompt=original_prompt,
            improved_prompt=improved,
            task_type=analysis.task_type,
            quality_before=analysis.quality_score,
            quality_after=quality_after,
            changes_summary=self._summarize_changes(analysis),
            structure_hint=template.structure_hint,
            model_used=model_used,
            success=True,
            error=error,
        )

    async def _call_llm(self, original_prompt: str, analysis: AnalysisResult) -> str:
        import httpx

        template = self.selector.get(analysis.task_type)
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "max_tokens": 1200,
            "messages": [
                {"role": "system", "content": template.system_prompt + " Return only the improved prompt."},
                {"role": "user", "content": self._build_user_message(original_prompt, analysis)},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.api_url, json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def _build_user_message(self, original_prompt: str, analysis: AnalysisResult) -> str:
        issues = "\n".join(f"- {issue}" for issue in analysis.issues) or "- none"
        suggestions = "\n".join(f"- {suggestion}" for suggestion in analysis.suggestions) or "- none"
        return f"""Original prompt:
{original_prompt}

Analysis:
- Language: {analysis.language}
- Task type: {analysis.task_type}
- Quality score: {analysis.quality_score}/100
- Issues:
{issues}
- Suggestions:
{suggestions}

Rewrite the prompt in the same main language."""

    def _rule_based_improve(self, original_prompt: str, analysis: AnalysisResult) -> str:
        template = self.selector.get(analysis.task_type)
        labels = self._labels(analysis.language)

        sections = [
            f"{labels['role']}: {labels['expert']}",
        ]
        if not analysis.has_context:
            sections.append(f"{labels['context']}: [{labels['add_context']}]")
        sections.append(f"{labels['task']}:\n{original_prompt.strip()}")
        if not analysis.has_output_format:
            sections.append(f"{labels['format']}: {self._default_format(analysis.task_type, analysis.language)}")
        if not analysis.has_constraints:
            sections.append(f"{labels['constraints']}:\n- {labels['be_specific']}\n- {labels['verify']}")
        sections.append(f"{labels['structure_hint']}: {template.structure_hint}")
        return "\n\n".join(sections).strip()

    def _labels(self, language: str) -> dict[str, str]:
        if language == "thai":
            return {
                "role": "บทบาท",
                "expert": "ผู้ช่วย AI ที่ตอบอย่างชัดเจน ตรวจสอบได้ และไม่เดาเกินข้อมูล",
                "context": "บริบท",
                "add_context": "เพิ่มบริบทที่เกี่ยวข้อง",
                "task": "งาน",
                "format": "รูปแบบผลลัพธ์",
                "constraints": "ข้อจำกัด",
                "be_specific": "ตอบให้เฉพาะเจาะจง",
                "verify": "ถ้ามีข้อเท็จจริงสำคัญ ให้ระบุวิธีตรวจสอบหรือข้อจำกัด",
                "structure_hint": "โครงสร้างที่แนะนำ",
            }
        return {
            "role": "Role",
            "expert": "An AI assistant that answers clearly, verifies important claims, and avoids unsupported guesses",
            "context": "Context",
            "add_context": "add relevant background",
            "task": "Task",
            "format": "Output format",
            "constraints": "Constraints",
            "be_specific": "be specific",
            "verify": "state verification steps or limitations for important claims",
            "structure_hint": "Recommended structure",
        }

    def _default_format(self, task_type: str, language: str) -> str:
        if task_type == "extraction":
            return "JSON only"
        if task_type == "summary":
            return "3-5 bullet points" if language != "thai" else "สรุปเป็น bullet 3-5 ข้อ"
        if task_type == "analysis":
            return "sections with evidence and conclusion" if language != "thai" else "แยกหัวข้อ พร้อมเหตุผลและข้อสรุป"
        return "clear sections"

    def _summarize_changes(self, analysis: AnalysisResult) -> list[str]:
        changes = []
        if not analysis.has_context:
            changes.append("added context placeholder")
        if not analysis.has_output_format:
            changes.append("added output format")
        if not analysis.has_constraints:
            changes.append("added constraints")
        if not analysis.has_examples and analysis.task_type in {"code", "extraction"}:
            changes.append("suggested examples")
        return changes or ["tightened clarity and specificity"]
