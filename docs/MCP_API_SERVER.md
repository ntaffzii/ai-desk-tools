# MCP API Server

คู่มือนี้อธิบายวิธีรัน `mcp-tools` เป็น MCP server แบบ API/HTTP แทน stdio

## Stdio กับ HTTP ต่างกันอย่างไร

```text
stdio = client เปิด process แล้วคุยผ่าน stdin/stdout
HTTP  = server เปิด port แล้ว client เชื่อมผ่าน network/local URL
```

ใช้ `stdio` เมื่อ:

- ใช้ Claude Desktop หรือ local MCP client ทั่วไป
- ต้องการ setup ง่ายที่สุด
- ไม่ต้องเปิด port

ใช้ `HTTP` เมื่อ:

- ต้องการให้หลาย agent/client เชื่อม server เดียวกัน
- ต้องการรันเป็น service
- ต้องการให้ local LLM framework หรือ app อื่นเรียกผ่าน URL
- ต้องการ deploy ในเครื่องหรือ private network

## ไฟล์ที่ใช้

```text
mcp-tools/server.py       = stdio MCP server
mcp-tools/server_http.py  = HTTP/SSE MCP server
```

ทั้งสองไฟล์ใช้ tools ชุดเดียวกันจาก:

```text
mcp-tools/tools/__init__.py
```

ดังนั้นเพิ่ม tool แค่ครั้งเดียว แล้วใช้ได้ทั้ง stdio และ HTTP

## ติดตั้ง

```powershell
cd C:\Users\natth\Documents\Skill-Agents\mcp-tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## รัน HTTP MCP Server

ค่า default:

```powershell
python .\server_http.py
```

จะพยายามรัน:

```text
transport = streamable-http
host      = 127.0.0.1
port      = 8765
```

กำหนดเอง:

```powershell
python .\server_http.py --transport streamable-http --host 127.0.0.1 --port 8765
```

ถ้า MCP runtime/client ของคุณใช้ SSE:

```powershell
python .\server_http.py --transport sse --host 127.0.0.1 --port 8765
```

หรือใช้ env:

```powershell
$env:MCP_HTTP_TRANSPORT="streamable-http"
$env:MCP_HTTP_HOST="127.0.0.1"
$env:MCP_HTTP_PORT="8765"
python .\server_http.py
```

## Provider Tokens

ตั้ง token ผ่าน environment ก่อนรัน:

```powershell
$env:NOTION_TOKEN="..."
$env:GITHUB_TOKEN="..."
$env:FIGMA_TOKEN="..."
$env:SLACK_BOT_TOKEN="..."
$env:POSTGRES_DSN="..."
python .\server_http.py
```

อย่าใส่ token จริงลง GitHub

## Client Config แนวคิด

MCP client แต่ละตัวใช้ config ไม่เหมือนกัน แต่หลักคือชี้ไปที่ URL ของ server:

```text
http://127.0.0.1:8765
```

ถ้า client ถาม transport:

```text
streamable-http
```

ถ้า client เก่ากว่าและรองรับ SSE:

```text
sse
```

## ใช้กับ Local LLM / Agent Framework

รูปแบบที่แนะนำ:

```text
Local LLM app
  -> skill loader อ่าน skills/**/SKILL.md
  -> MCP client เชื่อม http://127.0.0.1:8765
  -> เรียก tools ตาม workflow
```

ตัวอย่าง instruction ให้ local agent:

```text
You are connected to an MCP server at http://127.0.0.1:8765.
Select skills from skills/**/SKILL.md by description.
Use MCP tools only when needed.
Prefer read-only or draft-only tools for private data.
```

## Security

แนะนำ:

- ใช้ `127.0.0.1` ก่อน อย่าเปิด `0.0.0.0` ถ้ายังไม่ต้องการให้เครื่องอื่นเข้า
- ถ้าจะเปิด private network ให้มี auth/proxy/firewall
- อย่า expose server นี้บน public internet โดยตรง
- คง policy ใน `mcp-tools/config/tool_policy.json`
- รัน `mcp-security-audit` หลังเพิ่ม tools ใหม่

## Troubleshooting

ถ้า `streamable-http` ใช้ไม่ได้:

```powershell
python .\server_http.py --transport sse
```

ถ้า import `mcp` ไม่ได้:

```powershell
pip install -r requirements.txt
```

ถ้า Playwright ใช้ไม่ได้:

```powershell
playwright install chromium
```

ถ้า tool ที่ต้องใช้ token ขึ้นว่า missing:

```powershell
Get-ChildItem Env: | Where-Object { $_.Name -match 'NOTION|GITHUB|FIGMA|SLACK|POSTGRES' }
```

