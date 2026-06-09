# AI Desk Tools

Local MCP tools for personal AI agents.

This repo is the **executable MCP tool layer** for:

[ntaffzii/Skill-Agents](https://github.com/ntaffzii/Skill-Agents)

```text
Skill-Agents  = skills, workflows, docs, examples, provider config
ai-desk-tools = MCP server, Python tools, tests, runtime safety policy
```

Use this repo when you want LM Studio, Claude Desktop, Claude Code, Codex, or a local agent to call real tools on your machine.

## What It Includes

- MCP server over stdio: `server.py`
- MCP server over HTTP/SSE-style transport: `server_http.py`
- 50+ local tool groups
- skill routing and compact context building
- prompt improvement with local model fallback
- read-only/draft-only defaults for private data
- security policy and audit logging
- unit tests for tool behavior

## Companion Skill Repo

For skills, workflows, local LLM prompts, provider config, and usage docs:

[ntaffzii/Skill-Agents](https://github.com/ntaffzii/Skill-Agents)

Recommended pairing:

```text
Skill-Agents/examples/local-llm-agent-prompt.md
Skill-Agents/docs/SKILL_RUNTIME_FLOW.md
Skill-Agents/docs/LOCAL_LLM_SETTINGS.md
Skill-Agents/docs/PROMPT_IMPROVER_LOCAL_MODEL.md
Skill-Agents/config.json
```

## Quick Start

Clone:

```bash
git clone https://github.com/ntaffzii/ai-desk-tools.git
cd ai-desk-tools
```

Install:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Optional Playwright browser support:

```powershell
playwright install chromium
```

Run stdio MCP server:

```powershell
python .\server.py
```

Run HTTP MCP server:

```powershell
python .\server_http.py --host 127.0.0.1 --port 8765
```

Use `stdio` first unless your MCP client specifically supports HTTP MCP.

## LM Studio Setup

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

`LFM2.5-8B-A1B` is the recommended starter model for prompt improvement when available. It is not required.

## Claude Desktop Setup

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

## Environment Variables

Only set what you use. Do not commit real tokens.

```powershell
$env:NOTION_TOKEN="..."
$env:GITHUB_TOKEN="..."
$env:FIGMA_TOKEN="..."
$env:SLACK_BOT_TOKEN="..."
$env:POSTGRES_DSN="..."
$env:FIRECRAWL_API_KEY="..."
```

Prompt improver:

```powershell
$env:PROMPT_IMPROVER_API_URL="http://localhost:1234/v1/chat/completions"
$env:PROMPT_IMPROVER_MODEL="LFM2.5-8B-A1B"
```

If `PROMPT_IMPROVER_API_URL` is not set, prompt improvement still works with a rule-based fallback.

## Local LLM Flow

When paired with [Skill-Agents](https://github.com/ntaffzii/Skill-Agents), use this flow:

```text
User request
  -> skill-runtime.route_request
  -> prompt-improver if unclear
  -> skill-runtime.build_agent_context
  -> recommended toolset/tools
  -> final answer with verification
```

Example:

```text
Use skill-runtime first. Route this request, improve it only if unclear, then load selected workflow and skills:

Build today's plan from Notion, Obsidian, calendar, inbox, chat, memory, and open issues.
Draft only. Do not send or apply anything.
```

## Tool Groups

### Runtime And Routing

- `registry` - inspect tools, workflows, runtime capabilities, allowed roots, and policy.
- `skill-runtime` - index skills, route requests, load selected workflows/skills, and build compact local-LLM context.
- `toolsets` - recommend curated tool groups for job types.
- `audit` - inspect audit logs and policy denials.
- `mcp-security-audit` - classify MCP tools by risk and policy coverage.
- `system` - inspect environment and command availability.

### Project And Code

- `filesystem` - list, read, search, and inspect files.
- `project` - detect stack, scripts, important files, and health.
- `docs` - find documentation and build context bundles.
- `repo-index` - build and search lightweight repo maps.
- `package` - inspect manifests, dependencies, and lockfiles.
- `code-editing` - write, patch, preview diffs, format, and run tests.
- `validation` - plan and run allowlisted validation commands.
- `test-inspection` - find tests and map source to test files.
- `ci` - inspect CI files and validation commands.
- `structured-data` - read, validate, and patch JSON/YAML/TOML.
- `sandbox` - create temporary safe workspaces and compile snippets.

### Git And GitHub

- `git` - read-only Git status, diff, log, show, branch.
- `git-control` - create/switch branches, stage/unstage, commit.
- `github` - inspect local GitHub metadata and draft PR descriptions.
- `github-api` - read repo, issue, PR, changed files, and checks when token is configured.
- `issue-tracker` - parse issue references, draft issues, break down tasks, and plan updates.

### Backend And Security

- `api` - inspect routes, endpoints, OpenAPI, and API config.
- `database` - inspect schema files, migrations, ORM models, and database config.
- `postgres` - plan and run read-only Postgres queries when configured.
- `config` - inspect config files, env keys, and secret hygiene.
- `dependency-risk` - inspect dependency risk signals.
- `security-scanner` - scan for likely secrets, dangerous commands, env exposure, and dependency risks.
- `docker` - inspect Dockerfile/Compose and plan Docker validation.
- `release` - inspect versions, changelogs, and release readiness.
- `backup` - plan/create/list zip snapshots inside allowed roots.

### Personal Workspace

- `notion` - search/read Notion and draft page/block payloads.
- `obsidian-notion-bridge` - plan safe Obsidian/Notion conversions.
- `calendar` - summarize supplied events, build daily plans, draft meeting prep.
- `email-inbox` - summarize supplied email messages, extract action items, draft replies.
- `slack-discord` - search/summarize messages, draft replies, extract actions.
- `memory` - save/search/summarize local memories.
- `memory-context` - save typed decisions, preferences, lessons, and context packs.
- `vector-memory` - lightweight semantic memory search.
- `rag-adapter` - chunk text, plan RAG indexes, and draft embedding requests.

### Browser, Web, Media, Finance

- `browser` - inspect browser readiness, static HTML, and localhost URLs.
- `browser-page-map` - map HTML headings, links, forms, buttons, and inputs.
- `playwright` - inspect live pages and capture screenshots.
- `playwright-actions` - click/fill/assert text, inspect console/network, accessibility snapshots, persistent sessions.
- `figma` - inspect Figma files and draft frontend implementation plans.
- `web` - search/fetch/extract/summarize sources.
- `web-capture` - provider-neutral public webpage capture with social-site safety limits.
- `finance-market` - quotes, crypto prices, finance-news plans, watchlists, position risk.
- `media` - inspect/process images, audio, and video.
- `prompt-improver` - analyze, rewrite, score, and template prompts.
- `external-mcp-catalog` - compare public MCP patterns and draft local adaptations.
- `task` - scan TODO/FIXME/HACK/BUG markers and roadmap files.
- `user-runner` - write command handoffs and user-run PowerShell scripts.

## HTTP Server

```powershell
python .\server_http.py --transport streamable-http --host 127.0.0.1 --port 8765
```

If your client expects SSE:

```powershell
python .\server_http.py --transport sse --host 127.0.0.1 --port 8765
```

Keep `127.0.0.1` for personal use. Do not expose this server publicly without authentication, firewalling, per-user policy, and audit review.

## Safety Model

Defaults are intentionally conservative:

- Email/chat/issue/Notion actions are draft or plan oriented.
- Postgres rejects mutating SQL and only runs read-only queries.
- Web capture does not bypass login, CAPTCHA, private accounts, or paywalls.
- Git push, force push, reset hard, merge, and rebase are not exposed.
- File and command access are controlled by `config/tool_policy.json`.
- Audit logs are configured in `config/tool_policy.json`.

## Project Structure

```text
ai-desk-tools/
  README.md
  requirements.txt
  security.py
  server.py
  server_http.py
  trusted_sources.json
  config/
    tool_policy.json
  prompt_engine/
  tools/
  tests/
```

## Tests

```powershell
python -m unittest discover -s .\tests
```

If this repo is inside the full `Skill-Agents` workspace:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File ..\scripts\validate-all.ps1
```

## License

See `LICENSE` in the companion repo or add your preferred license file for this standalone tools repo.

