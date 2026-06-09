# Security Policy

`ai-desk-tools` is a local MCP server that may access files, commands, browser tooling, Git state, local memory, private workspace providers, and configured tokens. Treat it as sensitive local automation.

## Safe Defaults

- Bind HTTP mode to `127.0.0.1` for personal use.
- Keep private actions as draft-only or plan-only by default.
- Keep database access read-only.
- Keep web capture public-only.
- Do not expose the server directly to the public internet.
- Do not commit real tokens or `.env` files.

## Tool Policy

High-risk behavior is governed by:

```text
config/tool_policy.json
```

The policy controls:

- allowed filesystem roots
- audit log path
- allowed command prefixes
- blocked executables
- max read/output sizes

## Do Not Add Without Extra Review

- automatic email sending
- automatic chat posting
- broad Notion or Obsidian sync
- mutating database SQL
- Git push, force push, reset hard, merge, or rebase
- login bypass, CAPTCHA bypass, paywall bypass, or private social scraping
- token printing or unredacted secret reporting

## HTTP Server Warning

This is safe for local use:

```powershell
python .\server_http.py --host 127.0.0.1 --port 8765
```

This is risky without authentication and firewalling:

```powershell
python .\server_http.py --host 0.0.0.0 --port 8765
```

Tools run on the machine where the server process runs. If someone connects to your exposed server, they may be able to call tools against your machine unless policy and authentication are added.

## Reporting Or Fixing Issues

For private use, patch locally and rerun tests. Before publishing publicly, rotate any token that may have appeared in logs, screenshots, examples, or config.

Run:

```powershell
python -m unittest discover -s .\tests
```

