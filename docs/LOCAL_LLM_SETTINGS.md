# Local LLM Settings Guide

คู่มือนี้แนะนำค่าพารามิเตอร์สำหรับใช้ `Skill-Agents` กับ local LLM เช่น llama.cpp, LM Studio, Ollama, vLLM, text-generation-webui หรือ OpenAI-compatible local server

## หลักคิด

โปรเจกต์นี้ไม่ควรให้ local LLM อ่านทุกไฟล์พร้อมกัน แต่ควรใช้ flow:

```text
skill-runtime.route_request
  -> prompt_improver เฉพาะตอน prompt ไม่ชัด
  -> skill-runtime.build_agent_context
  -> เรียก MCP tools
```

ดังนั้น context ไม่จำเป็นต้องใหญ่มากตลอดเวลา แต่ควรมีพอสำหรับ:

- system prompt
- selected workflow
- selected skills
- user request
- tool results
- final answer

## ค่าแนะนำแบบเร็ว

| Use case | Context | Max output | Temperature | Top-p | Notes |
|---|---:|---:|---:|---:|---|
| Skill routing | 4k-8k | 512-1024 | 0.0-0.2 | 0.8-0.95 | ให้ deterministic |
| Prompt improver | 4k-8k | 1k-2k | 0.2-0.5 | 0.9 | ให้ rewrite ดีขึ้นแต่ไม่หลุด |
| Daily personal agent | 16k-32k | 2k-4k | 0.2-0.4 | 0.9 | ต้องรวม context หลายแหล่ง |
| Coding agent | 16k-32k | 2k-6k | 0.0-0.3 | 0.8-0.95 | เน้นแม่นและตรวจสอบได้ |
| Research report | 32k-64k | 4k-8k | 0.2-0.5 | 0.9 | มีหลาย source |
| Obsidian/Notion sync | 16k-32k | 2k-4k | 0.1-0.3 | 0.9 | ต้อง preserve metadata |
| RAG summarization | 32k-64k | 2k-6k | 0.1-0.4 | 0.9 | context เป็น chunks |
| Long planning | 32k+ | 4k-8k | 0.3-0.6 | 0.9 | ใช้เมื่อ brainstorming |

## ค่า Default ที่แนะนำสำหรับคุณ

ถ้าต้องเลือกชุดเดียวสำหรับใช้งานประจำ:

```text
context/window: 32768
max_output/new_tokens: 4096
temperature: 0.2
top_p: 0.9
top_k: 40
repeat_penalty: 1.05-1.12
presence_penalty: 0.0
frequency_penalty: 0.0
seed: fixed when debugging, random when writing
```

เหตุผล:

- 32k context พอสำหรับ workflow + skill + tool results หลายชุด
- temperature 0.2 ช่วยให้ agent ไม่หลุดจากกฎ
- 4k output พอสำหรับ plan/report/handoff ส่วนใหญ่
- repeat penalty นิดหน่อยช่วยลดการวนซ้ำ

## แยกค่าตามขั้นตอน Agent

### 1. Skill Runtime / Routing

ใช้ตอนเลือก workflow/skill/toolset

```text
context: 4096-8192
max_output: 512-1024
temperature: 0.0-0.2
top_p: 0.8-0.95
```

ไม่ต้องใช้ model ใหญ่ที่สุดก็ได้ เพราะงานคือ classification/routing

### 2. Prompt Improver

ใช้เมื่อ `route_request.needs_prompt_improver = true`

```text
context: 4096-8192
max_output: 1024-2048
temperature: 0.2-0.5
top_p: 0.9
```

ไม่ควรตั้ง temperature สูงเกิน เพราะ prompt จะเริ่มเปลี่ยนเจตนาเดิม

### 3. Tool Execution Reasoning

ใช้เมื่อต้องอ่านผลลัพธ์ tools และตัดสินใจ step ต่อไป

```text
context: 16384-32768
max_output: 1024-4096
temperature: 0.1-0.3
top_p: 0.9
```

### 4. Final Report / Handoff

ใช้ตอนสรุปผล

```text
context: 16384-32768
max_output: 2048-4096
temperature: 0.2-0.4
top_p: 0.9
```

## Context Budget สำหรับ Skill-Agents

แนะนำแบ่ง context แบบนี้เมื่อใช้ 32k:

```text
system/local-llm-agent-prompt: 2k-4k
workflow body: 2k-6k
selected skills: 4k-12k
tool registry/toolset summary: 2k-4k
tool results: 6k-12k
user request and conversation: 2k-6k
reserved output/headroom: 4k
```

ถ้า context แค่ 8k:

```text
system prompt: 1k
route result: 1k
one workflow: 2k
one skill: 2k
tool results: 1k
headroom: 1k
```

ถ้า context แค่ 4k:

```text
ใช้ route_request เท่านั้น
โหลด skill เดียว
สรุป tool results ให้สั้น
หลีกเลี่ยงหลาย source ใน prompt เดียว
```

## Model Size แนะนำ

### 3B-4B

เหมาะกับ:

- route request
- prompt improver เบื้องต้น
- summarize สั้น ๆ

ค่าแนะนำ:

```text
context: 4096-8192
temperature: 0.1-0.3
max_output: 512-1536
```

ไม่เหมาะกับงาน coding/research ยาว

### 7B-9B

เหมาะกับ:

- daily agent
- code edits เบา ๆ
- Obsidian/Notion planning
- tool routing

ค่าแนะนำ:

```text
context: 16384-32768
temperature: 0.1-0.3
max_output: 2048-4096
```

นี่คือ sweet spot สำหรับเครื่องส่วนตัวส่วนใหญ่

### 14B-32B

เหมาะกับ:

- coding ซับซ้อน
- review
- research synthesis
- multi-tool planning

ค่าแนะนำ:

```text
context: 32768-65536
temperature: 0.1-0.4
max_output: 4096-8192
```

ถ้าเครื่องรับไหว กลุ่มนี้จะใช้ Skill-Agents ได้ดีมาก

## llama.cpp / GGUF

ค่าที่เจอบ่อย:

```text
--ctx-size 32768
--temp 0.2
--top-p 0.9
--top-k 40
--repeat-penalty 1.08
--n-predict 4096
```

ถ้ามี VRAM พอ:

```text
--n-gpu-layers -1
```

ถ้าเริ่มช้า/กินแรม:

```text
--ctx-size 16384
--n-predict 2048
```

ถ้า model วนซ้ำ:

```text
--repeat-penalty 1.12
```

ถ้า model ตอบแข็งเกิน:

```text
--temp 0.3
```

ถ้า model เพ้อ:

```text
--temp 0.1
--top-p 0.8
```

## Ollama

ตัวอย่าง `Modelfile`:

```text
FROM qwen2.5-coder:7b

PARAMETER num_ctx 32768
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER top_k 40
PARAMETER repeat_penalty 1.08
```

รัน:

```powershell
ollama create skill-agent-local -f Modelfile
ollama run skill-agent-local
```

ถ้าใช้ OpenAI-compatible endpoint:

```powershell
$env:PROMPT_IMPROVER_API_URL="http://localhost:11434/v1/chat/completions"
$env:PROMPT_IMPROVER_MODEL="skill-agent-local"
```

## LM Studio

แนะนำ:

```text
Context length: 32768 ถ้า model/เครื่องรองรับ
Temperature: 0.2
Top P: 0.9
Repeat penalty: 1.08
Max tokens: 4096
```

เปิด local server แล้วตั้ง:

```powershell
$env:PROMPT_IMPROVER_API_URL="http://localhost:1234/v1/chat/completions"
$env:PROMPT_IMPROVER_MODEL="ชื่อโมเดลใน LM Studio"
```

## vLLM

เหมาะเมื่อมี GPU และต้องการ throughput

แนวคิด:

```text
max_model_len: 32768 หรือ 65536
temperature: 0.2
top_p: 0.9
max_tokens: 4096
```

ควรระวัง memory เพราะ context ยาวใช้ KV cache เยอะ

## RAG และ Chunk Settings

สำหรับ `rag-adapter`:

```text
chunk_size: 800-1200 สำหรับ notes ทั่วไป
chunk_size: 1200-2000 สำหรับ docs/report
overlap: 80-200
```

แนะนำ default:

```text
chunk_size: 1200
overlap: 120
```

ถ้า notes สั้น:

```text
chunk_size: 600
overlap: 60
```

ถ้า technical docs ยาว:

```text
chunk_size: 1800
overlap: 180
```

## Skill Runtime Context Settings

`build_agent_context` ใน `skill-runtime` มี default:

```text
max_chars: 24000
```

แนะนำ:

| Model context | build_agent_context max_chars |
|---:|---:|
| 4k | 6000-9000 |
| 8k | 12000-18000 |
| 16k | 20000-32000 |
| 32k | 24000-48000 |
| 64k | 48000-90000 |

สำหรับคุณ แนะนำ:

```text
build_agent_context max_chars: 24000-36000
```

ถ้า tool results เยอะ ให้ลดเหลือ:

```text
max_chars: 16000-24000
```

## Prompt Improver Local Model

ถ้าต้องการให้ `prompt_improver.py` ใช้ local model:

```powershell
$env:PROMPT_IMPROVER_API_URL="http://localhost:1234/v1/chat/completions"
$env:PROMPT_IMPROVER_MODEL="local-model-name"
```

ถ้าต้องเลือกหนึ่งตัวสำหรับงาน prompt improvement แนะนำ:

```powershell
$env:PROMPT_IMPROVER_MODEL="LFM2.5-8B-A1B"
```

ค่า generation สำหรับ prompt improver:

```text
temperature: 0.3
top_p: 0.9
max_output: 1024-2048
```

## ค่าที่ไม่แนะนำ

หลีกเลี่ยง:

```text
temperature > 0.8 สำหรับ coding/tools
context ใหญ่มากแต่ RAM/VRAM ไม่พอ
max_output สูงมากจน model พูดวน
โหลดทุก SKILL.md พร้อมกัน
เอา tool results ยาว ๆ เข้า prompt โดยไม่ summarize
```

## Troubleshooting

### Model ตอบเพ้อหรือไม่ทำตาม skill

ลด:

```text
temperature: 0.1-0.2
top_p: 0.8-0.9
```

เพิ่ม:

```text
ใช้ skill-runtime.build_agent_context แทนการ paste หลายไฟล์
```

### Model ลืม instruction

เพิ่ม:

```text
context size
system prompt ชัดขึ้น
โหลดเฉพาะ skill ที่เกี่ยวข้อง
```

ลด:

```text
tool results ที่ไม่จำเป็น
history เก่า
เอกสารยาวที่ไม่เกี่ยว
```

### Model วนซ้ำ

เพิ่ม:

```text
repeat_penalty 1.10-1.15
```

ลด:

```text
max_output
temperature
```

### ช้าเกินไป

ลด:

```text
ctx-size จาก 32768 เป็น 16384
max_output จาก 4096 เป็น 2048
จำนวน skills ที่โหลด
```

ใช้:

```text
route_request ก่อน
build_agent_context max_chars ต่ำลง
```

## Recommended Personal Presets

### Preset A: Daily Use

```text
context: 32768
max_output: 4096
temperature: 0.2
top_p: 0.9
top_k: 40
repeat_penalty: 1.08
build_agent_context: 24000
```

### Preset B: Fast Routing

```text
context: 8192
max_output: 1024
temperature: 0.1
top_p: 0.9
repeat_penalty: 1.05
```

### Preset C: Coding/Review

```text
context: 32768
max_output: 4096-8192
temperature: 0.1-0.2
top_p: 0.85-0.9
repeat_penalty: 1.08
```

### Preset D: Research/RAG

```text
context: 65536 ถ้าเครื่องไหว
max_output: 4096-8192
temperature: 0.2-0.4
top_p: 0.9
chunk_size: 1200-1800
overlap: 120-180
```

## สรุปสำหรับคุณ

เริ่มด้วยชุดนี้ก่อน:

```text
context: 32768
max_output: 4096
temperature: 0.2
top_p: 0.9
repeat_penalty: 1.08
build_agent_context max_chars: 24000
rag chunk_size: 1200
rag overlap: 120
```

แล้วใช้ flow:

```text
route_request
-> prompt_improver ถ้าจำเป็น
-> build_agent_context
-> tools
-> final answer
```
