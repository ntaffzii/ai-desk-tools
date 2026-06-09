"""Rule-based prompt analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass, field


TASK_TYPES = ("rag", "code", "creative", "qa", "summary", "extraction", "translation", "analysis", "general")

TASK_KEYWORDS: dict[str, list[str]] = {
    "rag": ["จากเอกสาร", "จากข้อมูล", "context", "based on", "from the document", "according to"],
    "code": ["เขียนโค้ด", "แก้บัก", "ฟังก์ชัน", "python", "javascript", "write code", "debug", "implement"],
    "creative": ["แต่งเรื่อง", "กลอน", "นิยาย", "creative", "story", "poem", "compose"],
    "summary": ["สรุป", "ย่อ", "summarize", "summary", "tldr", "brief"],
    "extraction": ["ดึงข้อมูล", "json", "yaml", "extract", "parse", "structured"],
    "translation": ["แปล", "translate", "english", "thai", "ภาษาอังกฤษ", "ภาษาไทย"],
    "analysis": ["วิเคราะห์", "เปรียบเทียบ", "ประเมิน", "analyze", "compare", "evaluate"],
    "qa": ["คืออะไร", "อธิบาย", "what is", "explain", "how does", "why"],
}

CONTEXT_SIGNALS = ["บริบท", "context", "background", "project", "ระบบ", "details"]
EXAMPLE_SIGNALS = ["ตัวอย่าง", "example", "for instance", "e.g.", "sample"]
FORMAT_SIGNALS = ["รูปแบบ", "format", "json", "yaml", "bullet", "table", "หัวข้อ", "list"]
CONSTRAINT_SIGNALS = ["ห้าม", "ต้อง", "ไม่เกิน", "must", "should not", "only", "limit", "within"]


@dataclass
class AnalysisResult:
    language: str = "unknown"
    task_type: str = "general"
    quality_score: int = 0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    word_count: int = 0
    has_context: bool = False
    has_examples: bool = False
    has_output_format: bool = False
    has_constraints: bool = False


class PromptAnalyzer:
    """Analyze a prompt before improvement."""

    def analyze(self, prompt: str) -> AnalysisResult:
        text = prompt.strip()
        result = AnalysisResult()
        if not text:
            result.issues.append("prompt is empty")
            result.suggestions.append("add the task, context, output format, and constraints")
            return result

        lower = text.lower()
        result.word_count = len(text.split())
        result.language = self._detect_language(text)
        result.task_type = self._detect_task_type(lower)
        result.has_context = any(signal in lower for signal in CONTEXT_SIGNALS)
        result.has_examples = any(signal in lower for signal in EXAMPLE_SIGNALS)
        result.has_output_format = any(signal in lower for signal in FORMAT_SIGNALS)
        result.has_constraints = any(signal in lower for signal in CONSTRAINT_SIGNALS)
        result.issues, result.suggestions = self._evaluate(result)
        result.quality_score = self._score(result)
        return result

    def _detect_language(self, text: str) -> str:
        thai_chars = len(re.findall(r"[\u0E00-\u0E7F]", text))
        ascii_words = len(re.findall(r"[a-zA-Z]+", text))
        total = max(1, len(text))
        if thai_chars / total > 0.45:
            return "thai"
        if thai_chars and ascii_words:
            return "mixed"
        return "english"

    def _detect_task_type(self, lower_text: str) -> str:
        scores = {task_type: 0 for task_type in TASK_TYPES}
        for task_type, keywords in TASK_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in lower_text:
                    scores[task_type] += 1
        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"

    def _evaluate(self, result: AnalysisResult) -> tuple[list[str], list[str]]:
        issues: list[str] = []
        suggestions: list[str] = []

        if result.word_count < 8:
            issues.append("prompt is too short")
            suggestions.append("add context, target audience, and expected output")
        if not result.has_context and result.task_type not in {"translation", "creative"}:
            issues.append("missing context")
            suggestions.append("state the background or situation")
        if not result.has_output_format and result.task_type in {"summary", "extraction", "rag", "analysis"}:
            issues.append("missing output format")
            suggestions.append("specify bullets, JSON, table, or section headings")
        if not result.has_examples and result.task_type in {"code", "extraction"}:
            issues.append("missing examples")
            suggestions.append("include input/output examples")
        if not result.has_constraints:
            issues.append("missing constraints")
            suggestions.append("add limits, exclusions, or must-have requirements")
        if result.language == "mixed":
            issues.append("mixed language may confuse the model")
            suggestions.append("keep one main language unless mixed output is intentional")

        return issues, suggestions

    def _score(self, result: AnalysisResult) -> int:
        score = 35
        score += 15 if result.has_context else 0
        score += 15 if result.has_examples else 0
        score += 15 if result.has_output_format else 0
        score += 10 if result.has_constraints else 0
        score += 5 if 8 <= result.word_count <= 250 else 0
        score -= len(result.issues) * 7
        return max(0, min(100, score))
