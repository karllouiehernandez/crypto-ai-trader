"""
MCP server entry point.

stdio mode — for Claude Code CLI (auto-discovered via .mcp.json):
    python run_mcp_server.py

SSE/HTTP mode — for remote access over SSH tunnel:
    python run_mcp_server.py --transport sse --port 8765
    MCP_TRANSPORT=sse MCP_PORT=8765 python run_mcp_server.py
"""
import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto AI Trader MCP Server")
    parser.add_argument(
        "--transport",
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        choices=["stdio", "sse"],
        help="Transport: stdio (default, Claude Code CLI) or sse (HTTP/remote)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "8765")),
        help="Port for SSE transport (default: 8765)",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="Host for SSE transport (default: 127.0.0.1)",
    )
    args = parser.parse_args()

    from mcp_server.server import mcp

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        import uvicorn
        app = mcp.sse_app()
        uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
