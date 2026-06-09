# Quickstart

Start `ai-desk-tools` as a local MCP server.

## 1. Install

```powershell
git clone https://github.com/ntaffzii/ai-desk-tools.git
cd ai-desk-tools
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional Playwright browser support:

```powershell
playwright install chromium
```

## 2. Run Stdio MCP Server

```powershell
python .\server.py
```

Use this mode first for LM Studio, Claude Desktop, Claude Code, and most local MCP clients.

## 3. LM Studio Config

In LM Studio:

```text
Program
-> Install
-> Edit mcp.json
```

Add:

```json
{
  "mcpServers": {
    "ai-desk-tools": {
      "command": "C:\\path\\to\\ai-desk-tools\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\path\\to\\ai-desk-tools\\server.py"
      ]
    }
  }
}
```

With prompt improver local model:

```json
{
  "mcpServers": {
    "ai-desk-tools": {
      "command": "C:\\path\\to\\ai-desk-tools\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\path\\to\\ai-desk-tools\\server.py"
      ],
      "env": {
        "PROMPT_IMPROVER_API_URL": "http://localhost:1234/v1/chat/completions",
        "PROMPT_IMPROVER_MODEL": "LFM2.5-8B-A1B"
      }
    }
  }
}
```

## 4. Optional Provider Tokens

Only set what you use:

```powershell
$env:NOTION_TOKEN="..."
$env:GITHUB_TOKEN="..."
$env:FIGMA_TOKEN="..."
$env:SLACK_BOT_TOKEN="..."
$env:POSTGRES_DSN="..."
$env:FIRECRAWL_API_KEY="..."
```

Do not commit real tokens.

## 5. Run HTTP MCP Server

Only use this when your client supports HTTP MCP:

```powershell
python .\server_http.py --transport streamable-http --host 127.0.0.1 --port 8765
```

If your client expects SSE:

```powershell
python .\server_http.py --transport sse --host 127.0.0.1 --port 8765
```

Keep `127.0.0.1` for personal use.

## 6. Test

```powershell
python -m unittest discover -s .\tests
```

## 7. Pair With Skills

For skills, workflows, prompts, provider config, and usage docs:

[ntaffzii/Skill-Agents](https://github.com/ntaffzii/Skill-Agents)

