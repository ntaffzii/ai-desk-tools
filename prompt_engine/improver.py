"""
improver.py
-----------
รับ prompt ดิบ + AnalysisResult แล้วเรียก LFM2.5-8B
เพื่อสร้าง improved prompt กลับมา
"""

import os
import json
import httpx
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from .analyzer import AnalysisResult
from .templates import TemplateSelector


# -----------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------

@dataclass
class ImproveResult:
    """ผลลัพธ์จากการ improve prompt"""
    original_prompt: str
    improved_prompt: str
    task_type: str
    quality_before: int
    quality_after: int          # ประมาณการ (วัดจาก analyzer อีกรอบ)
    changes_summary: list[str] = field(default_factory=list)
    structure_hint: str = ""
    model_used: str = "LFM2.5-8B-A1B"
    success: bool = True
    error: Optional[str] = None


# -----------------------------------------------------------------------
# PromptImprover
# -----------------------------------------------------------------------

class PromptImprover:
    """
    ส่ง prompt ไปให้ LFM ปรับปรุง

    ตัวอย่างการใช้งาน:
        improver = PromptImprover()
        result = await improver.improve(original_prompt, analysis_result)
        print(result.improved_prompt)
    """

    def __init__(
        self,
        api_url: str = "http://localhost:8080/v1/chat/completions",  # LFM local endpoint
        model: str = "LFM2.5-8B-A1B",
        timeout: int = 60,
        use_fallback: bool = True,          # fallback เป็น rule-based ถ้า API ไม่ตอบ
    ):
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.use_fallback = use_fallback
        self.selector = TemplateSelector()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def improve(
        self,
        original_prompt: str,
        analysis: AnalysisResult,
    ) -> ImproveResult:
        """
        ปรับปรุง prompt โดยใช้ LFM
        ถ้า API ไม่พร้อม จะใช้ rule-based fallback แทน
        """
        template = self.selector.get(analysis.task_type)

        try:
            improved = await self._call_llm(
                original_prompt=original_prompt,
                system_prompt=template.system_prompt,
                analysis=analysis,
            )
        except Exception as e:
            if self.use_fallback:
                improved = self._rule_based_improve(original_prompt, analysis)
                error_note = f"LFM API unavailable ({e}), used rule-based fallback"
            else:
                return ImproveResult(
                    original_prompt=original_prompt,
                    improved_prompt=original_prompt,
                    task_type=analysis.task_type,
                    quality_before=analysis.quality_score,
                    quality_after=analysis.quality_score,
                    success=False,
                    error=str(e),
                )
            error_note = None

        # ประมาณ quality หลัง improve
        quality_after = min(100, analysis.quality_score + max(10, (100 - analysis.quality_score) // 2))

        return ImproveResult(
            original_prompt=original_prompt,
            improved_prompt=improved,
            task_type=analysis.task_type,
            quality_before=analysis.quality_score,
            quality_after=quality_after,
            changes_summary=self._summarize_changes(analysis),
            structure_hint=template.structure_hint,
            model_used=self.model,
            success=True,
            error=getattr(self, "_last_error", None),
        )

    # ------------------------------------------------------------------
    # LFM API call
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        original_prompt: str,
        system_prompt: str,
        analysis: AnalysisResult,
    ) -> str:
        """เรียก LFM local endpoint (OpenAI-compatible)"""

        user_content = self._build_user_message(original_prompt, analysis)

        payload = {
            "model": self.model,
            "temperature": 0.3,
            "max_tokens": 1024,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()

    def _build_user_message(
        self, original_prompt: str, analysis: AnalysisResult
    ) -> str:
        """สร้าง user message ที่ส่งไปให้ LFM"""
        issues_text = "\n".join(f"- {i}" for i in analysis.issues) or "- ไม่พบปัญหาชัดเจน"
        suggestions_text = "\n".join(f"- {s}" for s in analysis.suggestions) or "- N/A"

        return f"""Please improve this prompt:

--- ORIGINAL PROMPT ---
{original_prompt}
--- END ---

Analysis:
- Language: {analysis.language}
- Task type: {analysis.task_type}
- Quality score: {analysis.quality_score}/100
- Issues found:
{issues_text}
- Suggestions:
{suggestions_text}

Rewrite the prompt to fix all the issues above. Keep the same language ({analysis.language})."""

    # ------------------------------------------------------------------
    # Rule-based fallback
    # ------------------------------------------------------------------

    def _rule_based_improve(
        self, original_prompt: str, analysis: AnalysisResult
    ) -> str:
        """
        ปรับ prompt แบบ rule-based เมื่อ LFM API ไม่พร้อม
        ใช้ template จาก templates.py + แทรก original prompt
        """
        template = self.selector.get(analysis.task_type)
        lang = analysis.language

        # สร้าง prefix ตามภาษา
        if lang == "thai":
            role_prefix = "คุณเป็น AI ผู้ช่วยที่เชี่ยวชาญ"
            task_label = "งาน"
            format_label = "รูปแบบคำตอบ"
            constraint_label = "ข้อจำกัด"
        else:
            role_prefix = "You are an expert AI assistant"
            task_label = "Task"
            format_label = "Output format"
            constraint_label = "Constraints"

        sections = [f"{role_prefix}\n"]

        # เพิ่ม context ถ้าขาด
        if not analysis.has_context:
            if lang == "thai":
                sections.append("บริบท: [ระบุบริบทที่เกี่ยวข้องที่นี่]\n")
            else:
                sections.append("Context: [Add relevant background here]\n")

        # ใส่ prompt เดิม
        sections.append(f"{task_label}:\n{original_prompt}\n")

        # เพิ่ม format ถ้าขาด
        if not analysis.has_output_format:
            if analysis.task_type == "extraction":
                sections.append(f"{format_label}: JSON\n")
            elif analysis.task_type == "summary":
                sections.append(f"{format_label}: bullet points (3-5 ข้อ)\n" if lang == "thai"
                                 else f"{format_label}: bullet points (3-5 items)\n")
            elif analysis.task_type == "rag":
                sections.append(f"{format_label}: ตอบจากเอกสารเท่านั้น ถ้าไม่พบให้บอกว่าไม่มีข้อมูล\n"
                                 if lang == "thai"
                                 else f"{format_label}: Answer from documents only. Say 'Not found' if absent.\n")

        return "\n".join(sections).strip()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _summarize_changes(self, analysis: AnalysisResult) -> list[str]:
        """สรุปสิ่งที่ถูกแก้ไขจากการ improve"""
        changes = []
        if not analysis.has_context:
            changes.append("เพิ่ม role และ context")
        if not analysis.has_output_format:
            changes.append("ระบุ output format")
        if not analysis.has_examples and analysis.task_type in ("extraction", "code"):
            changes.append("เพิ่มตัวอย่าง input/output")
        if not analysis.has_constraints:
            changes.append("เพิ่ม constraints")
        if analysis.language == "mixed":
            changes.append("ปรับภาษาให้สม่ำเสมอ")
        if not changes:
            changes.append("ปรับความชัดเจนและความเฉพาะเจาะจง")
        return changes