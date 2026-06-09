"""
analyzer.py
-----------
วิเคราะห์ prompt ที่รับเข้ามา หาจุดอ่อน และระบุประเภทงาน
ก่อนส่งต่อไปให้ improver.py
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# -----------------------------------------------------------------------
# Data classes
# -----------------------------------------------------------------------

@dataclass
class AnalysisResult:
    """ผลลัพธ์จากการวิเคราะห์ prompt"""

    # ภาษาหลักของ prompt
    language: str = "unknown"           # "thai" | "english" | "mixed"

    # ประเภทงาน
    task_type: str = "general"          # ดูค่าที่รองรับใน TASK_TYPES

    # คะแนนคุณภาพ 0–100 (ต่ำ = ต้องปรับปรุงมาก)
    quality_score: int = 0

    # รายการปัญหาที่พบ
    issues: list[str] = field(default_factory=list)

    # คำแนะนำสำหรับการปรับปรุง
    suggestions: list[str] = field(default_factory=list)

    # metadata เพิ่มเติม
    word_count: int = 0
    has_context: bool = False
    has_examples: bool = False
    has_output_format: bool = False
    has_constraints: bool = False


# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

TASK_TYPES = [
    "rag",          # ถามตอบจากเอกสาร
    "code",         # เขียน/แก้โค้ด
    "creative",     # งานสร้างสรรค์ เช่น บทกวี เรื่องสั้น
    "qa",           # ถามตอบทั่วไป
    "summary",      # สรุปเนื้อหา
    "extraction",   # ดึงข้อมูลเป็น JSON/YAML
    "translation",  # แปลภาษา
    "analysis",     # วิเคราะห์ข้อมูล
    "general",      # ทั่วไป / ยังระบุไม่ได้
]

# คำ keyword ที่ใช้ระบุประเภทงาน (ไทย + อังกฤษ)
TASK_KEYWORDS: dict[str, list[str]] = {
    "rag": [
        "จากเอกสาร", "จากข้อมูล", "จาก context", "ตามที่ระบุ",
        "based on", "from the document", "according to", "given the context",
    ],
    "code": [
        "เขียนโค้ด", "แก้บัก", "ฟังก์ชัน", "คลาส", "python", "javascript",
        "write code", "function", "class", "debug", "implement",
    ],
    "creative": [
        "แต่งเรื่อง", "เขียนบทกวี", "สร้างสรรค์", "กลอน", "นิยาย",
        "write a story", "poem", "creative", "fiction", "compose",
    ],
    "summary": [
        "สรุป", "ย่อ", "summarize", "tldr", "brief", "overview",
    ],
    "extraction": [
        "ดึงข้อมูล", "แปลงเป็น json", "extract", "parse", "structured",
        "json", "yaml", "xml",
    ],
    "translation": [
        "แปล", "translate", "ภาษาอังกฤษ", "ภาษาไทย", "english", "thai",
    ],
    "analysis": [
        "วิเคราะห์", "เปรียบเทียบ", "ประเมิน", "analyze", "compare",
        "evaluate", "assess",
    ],
    "qa": [
        "คืออะไร", "อธิบาย", "บอก", "what is", "explain", "tell me",
        "how does", "why",
    ],
}

# ตัวบ่งชี้ว่า prompt มีส่วนประกอบดีๆ
CONTEXT_SIGNALS = [
    "บริบท", "context", "background", "ข้อมูลเพิ่มเติม", "รายละเอียด",
    "ฉัน", "เรา", "โปรเจกต์", "ระบบ",
]
EXAMPLE_SIGNALS = [
    "ตัวอย่าง", "เช่น", "example", "for instance", "e.g.", "such as",
    "sample", "อย่างเช่น",
]
FORMAT_SIGNALS = [
    "รูปแบบ", "format", "json", "yaml", "หัวข้อ", "bullet", "list",
    "ตาราง", "table", "ข้อๆ", "numbered",
]
CONSTRAINT_SIGNALS = [
    "ไม่เกิน", "ห้าม", "ต้อง", "must", "should not", "limit",
    "max", "only", "ภายใน", "within",
]


# -----------------------------------------------------------------------
# PromptAnalyzer
# -----------------------------------------------------------------------

class PromptAnalyzer:
    """
    วิเคราะห์ prompt และคืน AnalysisResult

    ตัวอย่างการใช้งาน:
        analyzer = PromptAnalyzer()
        result = analyzer.analyze("สรุปเอกสารนี้ให้หน่อย")
        print(result.issues)
    """

    def analyze(self, prompt: str) -> AnalysisResult:
        """วิเคราะห์ prompt และคืน AnalysisResult"""
        prompt = prompt.strip()
        result = AnalysisResult()

        if not prompt:
            result.issues.append("prompt ว่างเปล่า")
            return result

        result.word_count = len(prompt.split())
        result.language = self._detect_language(prompt)
        result.task_type = self._detect_task_type(prompt)

        # ตรวจองค์ประกอบ
        lower = prompt.lower()
        result.has_context = any(s in lower for s in CONTEXT_SIGNALS)
        result.has_examples = any(s in lower for s in EXAMPLE_SIGNALS)
        result.has_output_format = any(s in lower for s in FORMAT_SIGNALS)
        result.has_constraints = any(s in lower for s in CONSTRAINT_SIGNALS)

        # สะสมปัญหาและคำแนะนำ
        result.issues, result.suggestions = self._evaluate(prompt, result)
        result.quality_score = self._score(result)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _detect_language(self, text: str) -> str:
        """ตรวจภาษาหลักของ prompt"""
        thai_chars = len(re.findall(r"[\u0E00-\u0E7F]", text))
        ascii_words = len(re.findall(r"[a-zA-Z]+", text))
        total = len(text)

        if total == 0:
            return "unknown"

        thai_ratio = thai_chars / total
        if thai_ratio > 0.5:
            return "thai"
        elif thai_ratio > 0.15:
            return "mixed"
        else:
            return "english"

    def _detect_task_type(self, prompt: str) -> str:
        """ระบุประเภทงานจาก keyword"""
        lower = prompt.lower()
        scores: dict[str, int] = {t: 0 for t in TASK_TYPES}

        for task, keywords in TASK_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    scores[task] += 1

        best = max(scores, key=lambda t: scores[t])
        return best if scores[best] > 0 else "general"

    def _evaluate(
        self, prompt: str, result: AnalysisResult
    ) -> tuple[list[str], list[str]]:
        """ตรวจสอบปัญหาและสร้างคำแนะนำ"""
        issues: list[str] = []
        suggestions: list[str] = []

        # 1. สั้นเกินไป
        if result.word_count < 5:
            issues.append("prompt สั้นเกินไป ขาดรายละเอียด")
            suggestions.append("เพิ่มบริบท เช่น คุณเป็นใคร งานนี้ทำเพื่ออะไร")

        # 2. ไม่มีบริบท
        if not result.has_context and result.task_type not in ("translation", "creative"):
            issues.append("ขาดบริบทหรือข้อมูลพื้นฐาน")
            suggestions.append("ระบุบริบท เช่น 'คุณเป็น developer ที่กำลังทำ...'")

        # 3. ไม่ระบุรูปแบบผลลัพธ์
        if not result.has_output_format and result.task_type in ("extraction", "rag", "summary"):
            issues.append("ไม่ระบุรูปแบบผลลัพธ์ที่ต้องการ")
            suggestions.append("ระบุ format เช่น 'ตอบเป็น JSON', 'สรุป 3 ข้อ'")

        # 4. RAG ไม่มีเอกสาร
        if result.task_type == "rag" and "<doc" not in prompt.lower():
            issues.append("งาน RAG ควรแนบเอกสารใน prompt")
            suggestions.append("ใส่เอกสารในรูปแบบ <document1>...</document1>")

        # 5. ภาษาผสมกัน
        if result.language == "mixed":
            issues.append("ใช้ภาษาไทยและอังกฤษปนกัน อาจทำให้โมเดลสับสน")
            suggestions.append("เลือกใช้ภาษาเดียวให้สม่ำเสมอ")

        # 6. ไม่มีตัวอย่าง (สำหรับงาน extraction/code)
        if not result.has_examples and result.task_type in ("extraction", "code"):
            issues.append("ไม่มีตัวอย่าง input/output")
            suggestions.append("เพิ่มตัวอย่างเพื่อให้โมเดลเข้าใจ pattern ที่ต้องการ")

        # 7. ยาวเกินไป (อาจมี noise)
        if result.word_count > 500:
            issues.append("prompt ยาวมาก อาจมีข้อมูลที่ไม่จำเป็น")
            suggestions.append("ตัดส่วนที่ไม่เกี่ยวข้องออก และจัดลำดับความสำคัญ")

        return issues, suggestions

    def _score(self, result: AnalysisResult) -> int:
        """คำนวณคะแนนคุณภาพ 0–100"""
        score = 40  # คะแนนฐาน

        # บวกคะแนนจากองค์ประกอบที่มี
        if result.has_context:
            score += 15
        if result.has_examples:
            score += 15
        if result.has_output_format:
            score += 15
        if result.has_constraints:
            score += 10

        # ลดคะแนนตามจำนวนปัญหา
        score -= len(result.issues) * 8

        # ความยาวที่เหมาะสม
        if 10 <= result.word_count <= 200:
            score += 5

        return max(0, min(100, score))