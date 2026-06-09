"""AI Desk Tools MCP HTTP server.

Run this file when an MCP client supports an HTTP-style transport instead of
stdio. The default transport is ``streamable-http`` because it is the modern
MCP HTTP transport in current FastMCP-style servers. If your installed MCP
runtime expects SSE, set ``MCP_HTTP_TRANSPORT=sse``.
"""

from __future__ import annotations

import argparse
import os

from mcp.server.fastmcp import FastMCP

from tools import register_all_tools


def build_server() -> FastMCP:
    """Build and register the AI Desk Tools MCP server."""
    server = FastMCP("AI Desk Tools")
    register_all_tools(server)
    return server


def main() -> None:
    """Run the MCP server over an HTTP-capable transport."""
    parser = argparse.ArgumentParser(description="Run AI Desk Tools MCP over HTTP transport.")
    parser.add_argument("--transport", default=os.getenv("MCP_HTTP_TRANSPORT", "streamable-http"), help="HTTP transport to use: streamable-http or sse.")
    parser.add_argument("--host", default=os.getenv("MCP_HTTP_HOST", "127.0.0.1"), help="Host/interface for HTTP server.")
    parser.add_argument("--port", type=int, default=int(os.getenv("MCP_HTTP_PORT", "8765")), help="Port for HTTP server.")
    args = parser.parse_args()

    server = build_server()
    server.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()

