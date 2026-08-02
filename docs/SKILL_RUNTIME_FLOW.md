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

## Scoring: TF-IDF cosine similarity

`recommend_workflows` / `recommend_skills` / `recommend_toolsets` rank candidates using TF-IDF cosine similarity between the task description and each item's `name + description (+ tags)` text, computed fresh over the candidate pool on every call (`_cosine_score_batch` in `tools/skill_runtime.py`). This replaced a plain token-overlap counter:

- **IDF weighting**: a distinctive word shared with only a few items (e.g. "promptpay", "withholding") counts for more than a word shared with most items (e.g. "use", "skill", "task").
- **Cosine normalization**: score reflects vector *direction* (proportion of shared meaningful terms), not raw count — a long, mostly-irrelevant description no longer outscores a short, precisely relevant one just by sharing a few common words.
- Structural bonuses (a skill already named by a matched workflow, a toolset already recommended by the primary matched workflow) are added **on top of** the cosine score, not blended into it — see `_recommend_skills`/`_recommend_toolsets`.

**What this is not**: still a *lexical* (shared-token) similarity, no dependencies, runs offline. It will not match a query and a description that mean the same thing but share no literal token (a synonym, a cross-language paraphrase, an abbreviation the tokenizer doesn't recognize). If that turns out to matter in practice, the upgrade path is a real embedding model (e.g. a local `sentence-transformers` model, or an Ollama embedding endpoint) swapped in for `_cosine_score_batch` — same call signature (`query, haystacks -> list[float]`), different vector source.

## Safety

- `skill-runtime` อ่านเฉพาะไฟล์ใน repo
- `route_request` ไม่เรียก external provider
- `build_agent_context` จำกัดขนาด context
- ใช้ `prompt_improver` เฉพาะเมื่อ prompt สั้นหรือไม่ชัด
- private actions ยังต้องเป็น read-only/draft-only ตาม skill และ tool policy

