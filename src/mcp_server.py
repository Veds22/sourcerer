"""
Remote MCP server for sourcerer (Streamable HTTP transport).

Exposes the same FastMCP instance and tools as src/mcp.py (stdio),
but over HTTP so that src/llm.py's webhook-side Groq loop can connect
to it as an MCP client.

Run with:
    uv run python -m src.mcp_server
"""

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.mcp import mcp

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8001, path="/mcp")