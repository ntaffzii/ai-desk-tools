# HTTP MCP Client Notes

Run HTTP MCP server:

```powershell
cd C:\Users\natth\Documents\Skill-Agents\mcp-tools
.\.venv\Scripts\Activate.ps1
python .\server_http.py --transport streamable-http --host 127.0.0.1 --port 8765
```

If your client expects SSE:

```powershell
python .\server_http.py --transport sse --host 127.0.0.1 --port 8765
```

Client URL:

```text
http://127.0.0.1:8765
```

Security notes:

- Keep `127.0.0.1` for personal use.
- Do not expose this server publicly without auth, firewall, per-user policy, and audit review.
- Tools run on the machine where `server_http.py` is running.

