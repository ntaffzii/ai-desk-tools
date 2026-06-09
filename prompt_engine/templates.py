"""
templates.py
------------
เก็บ system prompt template และ prompt structure
สำหรับงานแต่ละประเภท ใช้คู่กับ improver.py
"""

from dataclasses import dataclass
from typing import Optional


# -----------------------------------------------------------------------
# Data class
# -----------------------------------------------------------------------

@dataclass
class PromptTemplate:
    """template สำหรับงานหนึ่งประเภท"""
    task_type: str
    system_prompt: str          # system prompt สำหรับ LFM ตอน improve
    structure_hint: str         # คำใบ้โครงสร้าง prompt ที่ดี
    example_improved: str       # ตัวอย่าง prompt ที่ improve แล้ว


# -----------------------------------------------------------------------
# Templates
# -----------------------------------------------------------------------

TEMPLATES: dict[str, PromptTemplate] = {

    "rag": PromptTemplate(
        task_type="rag",
        system_prompt="""You are an expert prompt engineer specializing in RAG (Retrieval-Augmented Generation) systems.
Improve the given prompt to:
1. Clearly specify where the model should look for information (from provided documents only)
2. Include instruction to avoid hallucination
3. Define output format clearly
4. Add instruction to cite sources when possible
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง RAG prompt ที่ดี:
[Role] คุณเป็น... ตอบคำถามจากเอกสารที่ให้มาเท่านั้น
[Documents] <document1>...</document1>
[Task] คำถาม/งานที่ต้องการ
[Format] รูปแบบคำตอบที่ต้องการ
[Constraint] ห้ามตอบนอกเอกสาร / ถ้าไม่รู้ให้บอกว่าไม่มีข้อมูล""",
        example_improved="""คุณเป็น AI ผู้ช่วยที่ตอบคำถามจากเอกสารที่ให้มาเท่านั้น ห้ามสร้างข้อมูลขึ้นเอง

<document1>
{เนื้อหาเอกสาร}
</document1>

คำถาม: {คำถาม}

ตอบโดย:
1. อ้างอิงจากเอกสารข้างต้นเท่านั้น
2. ถ้าไม่มีข้อมูลในเอกสาร ให้ตอบว่า "ไม่พบข้อมูลในเอกสารที่ให้มา"
3. ระบุส่วนของเอกสารที่ใช้อ้างอิง""",
    ),

    "code": PromptTemplate(
        task_type="code",
        system_prompt="""You are an expert prompt engineer for coding tasks.
Improve the given prompt to:
1. Specify programming language and version
2. Define input/output clearly with examples
3. Add constraints (performance, style, libraries)
4. Request explanation of the solution
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง Code prompt ที่ดี:
[Language] ภาษา + version
[Task] งานที่ต้องทำ
[Input] ตัวอย่าง input
[Output] ตัวอย่าง output ที่ต้องการ
[Constraints] ข้อจำกัด เช่น ห้ามใช้ library นอก stdlib
[Style] รูปแบบ เช่น type hint, docstring""",
        example_improved="""เขียน Python 3.11 function สำหรับ {งาน}

Input: {ตัวอย่าง input}
Expected Output: {ตัวอย่าง output}

Requirements:
- ใส่ type hints ทุก argument และ return value
- เขียน docstring อธิบาย function
- handle edge case: {edge cases}
- ห้ามใช้ library นอก standard library

หลังเขียนโค้ดแล้ว อธิบายสั้นๆ ว่า logic ทำงานอย่างไร""",
    ),

    "summary": PromptTemplate(
        task_type="summary",
        system_prompt="""You are an expert prompt engineer for summarization tasks.
Improve the given prompt to:
1. Specify summary length or format (bullets, paragraph, etc.)
2. Define what aspects to focus on
3. Specify target audience
4. Request key takeaways
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง Summary prompt ที่ดี:
[Role] ผู้รับ summary คือใคร
[Content] เนื้อหาที่ต้องสรุป
[Focus] ประเด็นที่ต้องเน้น
[Format] รูปแบบ เช่น 3 bullet points / 1 paragraph
[Length] ความยาวที่ต้องการ""",
        example_improved="""สรุปเนื้อหาต่อไปนี้สำหรับ {กลุ่มเป้าหมาย}

{เนื้อหา}

รูปแบบการสรุป:
- สรุปประเด็นหลัก 3-5 ข้อ (bullet points)
- แต่ละข้อไม่เกิน 2 ประโยค
- เน้น {ประเด็นสำคัญ}
- สรุป key takeaway 1 ประโยคท้ายสุด""",
    ),

    "extraction": PromptTemplate(
        task_type="extraction",
        system_prompt="""You are an expert prompt engineer for data extraction tasks.
Improve the given prompt to:
1. Define exact JSON/YAML schema with field descriptions
2. Specify how to handle missing data
3. Add validation rules
4. Request only structured output (no prose)
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง Extraction prompt ที่ดี:
[Task] ดึงข้อมูลตาม schema ต่อไปนี้
[Schema] JSON schema พร้อม description แต่ละ field
[Rules] กฎเพิ่มเติม เช่น ถ้าไม่มีข้อมูลให้ใส่ null
[Output] Return JSON เท่านั้น ห้ามมี prose""",
        example_improved="""ดึงข้อมูลจากข้อความต่อไปนี้และ return เป็น JSON ตาม schema ที่กำหนด

ข้อความ: {ข้อความ}

Schema:
{
  "field_name": "คำอธิบาย field",
  "nested": {
    "sub_field": "คำอธิบาย"
  }
}

Rules:
- ถ้าไม่พบข้อมูล ให้ใส่ null
- ห้ามเพิ่ม field ที่ไม่อยู่ใน schema
- Return JSON เท่านั้น ไม่ต้องมีคำอธิบาย""",
    ),

    "translation": PromptTemplate(
        task_type="translation",
        system_prompt="""You are an expert prompt engineer for translation tasks.
Improve the given prompt to:
1. Specify source and target language clearly
2. Define tone and formality level
3. Note domain-specific terms to preserve
4. Request natural, native-sounding output
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง Translation prompt ที่ดี:
[Source] ภาษาต้นทาง
[Target] ภาษาปลายทาง
[Tone] ทางการ / กึ่งทางการ / ไม่ทางการ
[Domain] สาขา เช่น เทคนิค / การแพทย์ / ธุรกิจ
[Preserve] คำที่ไม่ต้องแปล เช่น ชื่อเฉพาะ""",
        example_improved="""แปลข้อความต่อไปนี้จาก {ภาษาต้นทาง} เป็น {ภาษาปลายทาง}

ข้อความ: {ข้อความ}

เงื่อนไข:
- ใช้ภาษา{ระดับ ทางการ/ไม่ทางการ}
- รักษาความหมายเดิมให้ครบถ้วน
- คำศัพท์เฉพาะทาง: {คำที่ต้องคงไว้}
- ให้ฟังดูเป็นธรรมชาติสำหรับเจ้าของภาษา""",
    ),

    "analysis": PromptTemplate(
        task_type="analysis",
        system_prompt="""You are an expert prompt engineer for analytical tasks.
Improve the given prompt to:
1. Define the analytical framework to use
2. Specify what dimensions to analyze
3. Request evidence-based reasoning
4. Define output structure (pros/cons, SWOT, etc.)
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง Analysis prompt ที่ดี:
[Role] ผู้เชี่ยวชาญด้านใด
[Subject] สิ่งที่วิเคราะห์
[Framework] กรอบการวิเคราะห์
[Dimensions] มิติที่ต้องพิจารณา
[Output] รูปแบบผลลัพธ์ เช่น SWOT, pros/cons""",
        example_improved="""วิเคราะห์ {หัวข้อ} ในฐานะผู้เชี่ยวชาญด้าน {สาขา}

ข้อมูล: {ข้อมูล}

วิเคราะห์ใน 4 มิติ:
1. จุดแข็ง (Strengths)
2. จุดอ่อน (Weaknesses)
3. โอกาส (Opportunities)
4. ภัยคุกคาม (Threats)

สำหรับแต่ละมิติ:
- ระบุ 2-3 ประเด็น พร้อมเหตุผลสนับสนุน
- อ้างอิงจากข้อมูลที่ให้มา
- สรุปข้อเสนอแนะท้ายสุด""",
    ),

    "creative": PromptTemplate(
        task_type="creative",
        system_prompt="""You are an expert prompt engineer for creative writing tasks.
Improve the given prompt to:
1. Set the tone, mood, and style clearly
2. Define characters, setting, and conflict if applicable
3. Specify length and format
4. Add constraints that spark creativity
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง Creative prompt ที่ดี:
[Genre] ประเภทงาน เช่น กลอน / เรื่องสั้น
[Tone] อารมณ์ที่ต้องการ
[Elements] องค์ประกอบที่ต้องมี
[Length] ความยาว
[Style] สไตล์การเขียน""",
        example_improved="""แต่ง {ประเภทงาน} ในสไตล์ {สไตล์}

โจทย์: {หัวข้อ}

เงื่อนไข:
- อารมณ์: {อารมณ์}
- ความยาว: {ความยาว}
- ต้องมีองค์ประกอบ: {องค์ประกอบ}
- ห้ามใช้คำซ้ำมากกว่า 3 ครั้ง""",
    ),

    "qa": PromptTemplate(
        task_type="qa",
        system_prompt="""You are an expert prompt engineer for question-answering tasks.
Improve the given prompt to:
1. Be specific about what information is needed
2. Define the depth of answer required
3. Specify the audience's knowledge level
4. Request structured response when appropriate
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง QA prompt ที่ดี:
[Role] คุณเป็น...
[Question] คำถามที่ชัดเจน
[Context] บริบทที่เกี่ยวข้อง
[Depth] ระดับความลึกที่ต้องการ
[Audience] ผู้รับข้อมูลเป็นใคร""",
        example_improved="""อธิบาย {หัวข้อ} สำหรับ {กลุ่มเป้าหมาย}

บริบท: {บริบทเพิ่มเติม}

โปรดตอบโดย:
1. อธิบายหลักการพื้นฐานก่อน
2. ยกตัวอย่างที่เข้าใจง่าย
3. ระบุข้อควรระวังหรือข้อยกเว้น
4. สรุปใน 1-2 ประโยค""",
    ),

    "general": PromptTemplate(
        task_type="general",
        system_prompt="""You are an expert prompt engineer.
Improve the given prompt to be clearer, more specific, and more likely to get a great response.
Focus on:
1. Clarity - remove ambiguity
2. Context - add relevant background
3. Specificity - define expected output
4. Constraints - add helpful boundaries
Respond with ONLY the improved prompt, no explanation.""",
        structure_hint="""โครงสร้าง prompt ที่ดีโดยทั่วไป:
[Role] คุณเป็นใคร / โมเดลควรรับบทบาทอะไร
[Context] บริบทที่เกี่ยวข้อง
[Task] งานที่ต้องการอย่างชัดเจน
[Format] รูปแบบผลลัพธ์
[Constraints] ข้อจำกัดที่มี""",
        example_improved="""คุณเป็น {บทบาท} ที่มีความเชี่ยวชาญด้าน {สาขา}

บริบท: {บริบท}

งาน: {งานที่ต้องการอย่างชัดเจน}

ตอบในรูปแบบ: {รูปแบบ}
ความยาวประมาณ: {ความยาว}""",
    ),
}


# -----------------------------------------------------------------------
# TemplateSelector
# -----------------------------------------------------------------------

class TemplateSelector:
    """เลือก template ที่เหมาะสมกับ task_type"""

    def get(self, task_type: str) -> PromptTemplate:
        """คืน template สำหรับ task_type ที่ระบุ ถ้าไม่พบใช้ 'general'"""
        return TEMPLATES.get(task_type, TEMPLATES["general"])

    def get_system_prompt(self, task_type: str) -> str:
        return self.get(task_type).system_prompt

    def get_structure_hint(self, task_type: str) -> str:
        return self.get(task_type).structure_hint

    def list_task_types(self) -> list[str]:
        return list(TEMPLATES.keys())