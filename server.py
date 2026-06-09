"""AI Desk Tools MCP server.

Run this file with stdio transport from an MCP client such as Claude Desktop,
Codex, or another MCP-aware agent.
"""

from mcp.server.fastmcp import FastMCP

from tools import register_all_tools


mcp = FastMCP("AI Desk Tools")
register_all_tools(mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio")
