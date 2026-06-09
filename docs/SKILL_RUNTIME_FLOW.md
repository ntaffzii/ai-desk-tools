# Skill Runtime Flow

เอกสารนี้อธิบายว่า local LLM หรือ provider ที่ไม่มี native skill loader ควรใช้ skills, workflows, prompt improver และ MCP tools ร่วมกันอย่างไร

## คำตอบสั้น

ไม่ควรให้ LLM อ่านทุก skill เต็ม ๆ ทุกครั้ง

ควรใช้ลำดับนี้:

```text
User request
  -> skill-runtime.route_request
  -> ถ้า prompt ไม่ชัด ใช้ prompt_improver
  -> skill-runtime.load_workflow / load_skill เฉพาะที่เลือก
  -> เลือก toolset/tools
  -> ทำงาน
```

## บทบาทของแต่ละส่วน

```text
Skill Runtime    = เลือก skill/workflow/toolset และ build context
Prompt Improver  = ปรับ prompt เมื่อคำสั่งคลุมเครือ
Skills           = วิธีคิดและกฎการทำงาน
Workflows        = ลำดับงาน
Toolsets         = กลุ่ม tools ที่ควรใช้
MCP Tools        = ลงมือทำจริง
```

## Tool Group ใหม่

`skill-runtime` มี tools:

- `build_skill_index`
- `recommend_workflows`
- `recommend_skills`
- `load_skill`
- `load_workflow`
- `route_request`
- `build_agent_context`

## Flow ปกติ

### กรณี user request ชัด

```text
User:
Use personal-knowledge-sync. Treat Obsidian as source of truth and draft Notion payloads only.

Agent:
1. route_request
2. load_workflow personal-knowledge-sync
3. load_skill obsidian-notion-bridge
4. use personal-knowledge-rag toolset
5. call filesystem / obsidian-notion-bridge / notion / rag-adapter
```

### กรณี user request ไม่ชัด

```text
User:
จัดให้หน่อย

Agent:
1. route_request
2. sees needs_prompt_improver = true
3. call prompt_improver.analyze_prompt
4. ask a short clarification or improve prompt
5. route again
```

### กรณี user ขอปรับ prompt โดยตรง

```text
User:
ช่วยปรับ prompt นี้ให้ดีขึ้น

Agent:
1. use prompt_improver directly
2. no need to load skills unless prompt is for a specific workflow
```

## Local LLM System Prompt

ใช้ร่วมกับ `examples/local-llm-agent-prompt.md`

เพิ่ม rule นี้:

```text
Before loading any full SKILL.md file:
1. Call skill-runtime.route_request when available.
2. If needs_prompt_improver is true, improve or clarify the prompt first.
3. Load only selected workflow and skill files.
4. Use recommended toolsets before individual tools.
```

## Pseudocode สำหรับ Local Agent

```python
request = user_input

route = mcp.call("route_request", {"task_description": request})

if route["needs_prompt_improver"]:
    improved = mcp.call("improve_prompt", {"prompt": request})
    request = improved["improved_prompt"]
    route = mcp.call("route_request", {"task_description": request})

context = mcp.call("build_agent_context", {"task_description": request})

model_input = system_prompt + context["context"] + request
answer = llm.generate(model_input)
```

## เมื่อไหร่ควรใช้ `build_agent_context`

ใช้เมื่อ:

- provider ไม่มี native skill loader
- local LLM ต้องการ context สำเร็จรูป
- อยากโหลด workflow + skill ที่เกี่ยวข้องแบบ compact

ไม่จำเป็นเมื่อ:

- agent รองรับ skills อยู่แล้ว
- ผู้ใช้เรียก skill ชัดเจนและ runtime โหลดให้เอง
- งานเป็น prompt-improvement อย่างเดียว

## ตัวอย่าง Prompt

```text
Use skill-runtime first.
Route this request, improve it only if unclear, then load the selected workflow and skills:

Build today's plan from Notion, Obsidian, calendar, inbox, chat, memory, and open issues.
Draft only. Do not send or apply anything.
```

## Safety

- `skill-runtime` อ่านเฉพาะไฟล์ใน repo
- `route_request` ไม่เรียก external provider
- `build_agent_context` จำกัดขนาด context
- ใช้ `prompt_improver` เฉพาะเมื่อ prompt สั้นหรือไม่ชัด
- private actions ยังต้องเป็น read-only/draft-only ตาม skill และ tool policy

